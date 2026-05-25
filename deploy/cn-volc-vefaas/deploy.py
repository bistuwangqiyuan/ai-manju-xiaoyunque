#!/usr/bin/env python3
"""火山引擎 veFaaS 一键部署脚本.

参考官方文档:
  - https://www.volcengine.com/docs/6662/1262132  (CreateFunction OpenAPI)
  - https://www.volcengine.com/docs/6662/116910   (部署方法)
  - https://agentkit.gitbook.io/docs/deploy/to-vefaas

工作流:
  1. 读取环境变量 / config.yaml 拿 AKSK / region / 镜像 tag
  2. (可选) 调 ``docker build`` + ``docker push`` 推镜像到火山镜像仓库
  3. 调火山 OpenAPI ``Action=CreateFunction`` 创建/更新函数
  4. 调火山 OpenAPI ``Action=CreateRelease`` 发布版本
  5. (可选) 创建 API 网关路由 (Action=CreateRoute)
  6. 输出最终公网 URL

依赖: 仅 stdlib + (可选) PyYAML / 已有 boto3 在 backend/requirements.txt

用法::

    # 推荐: 用环境变量
    python deploy/cn-volc-vefaas/deploy.py --image xyq:v9 --build --push

    # dry-run: 不真正调用 OpenAPI, 仅打印 payload
    python deploy/cn-volc-vefaas/deploy.py --dry-run

    # 仅创建函数, 不重新构建镜像 (基于已有 tag)
    python deploy/cn-volc-vefaas/deploy.py --image-tag v9.0.1
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import hmac
import json
import logging
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# 让 deploy.py 既能在仓库根 (``python deploy/cn-volc-vefaas/deploy.py``) 跑,
# 也能在自身目录 (``cd deploy/cn-volc-vefaas && python deploy.py``) 跑.
# ---------------------------------------------------------------------------
_THIS = pathlib.Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Constants — 火山 OpenAPI 契约
# ---------------------------------------------------------------------------
VEFAAS_HOST = "open.volcengineapi.com"
VEFAAS_VERSION = "2024-06-06"
VEFAAS_SERVICE = "vefaas"
VEAPIG_SERVICE = "apig"
DEFAULT_REGION = "cn-beijing"
DEFAULT_RUNTIME = "native/v1"
DEFAULT_CPU = 1.0
DEFAULT_MEMORY_MB = 2048
DEFAULT_TIMEOUT_SECS = 900           # veFaaS 同步 max 15 min; 异步可达 24h
DEFAULT_INITIALIZER_SECS = 60

_log = logging.getLogger("deploy_vefaas")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


_PLACEHOLDER_PATTERNS = (
    "<paste-", "<paste_", "REPLACE_ME", "your-", "YOUR_",
    "xxxx", "placeholder", "{{", "${",
)


def _is_placeholder(v: str) -> bool:
    if not v or len(v) < 4:
        return True
    s = v.strip()
    for pat in _PLACEHOLDER_PATTERNS:
        if pat in s:
            return True
    return False


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sign_volc_v4(ak: str, sk: str, service: str, region: str, host: str,
                  method: str, query: dict, body: bytes,
                  *, content_type: str = "application/json; charset=utf-8") -> dict:
    """火山 OpenAPI HMAC-SHA256 V4 签名 (与 Volc Visual API 同算法).

    参考: https://www.volcengine.com/docs/6369/67269
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    body_hash = _sha256_hex(body)

    canonical_query_pairs = sorted(query.items())
    canonical_query = "&".join(
        urllib.parse.quote(str(k), safe="-_.~") + "=" + urllib.parse.quote(str(v), safe="-_.~")
        for k, v in canonical_query_pairs
    )

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{amzdate}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join([
        method.upper(),
        "/",
        canonical_query,
        canonical_headers,
        signed_headers,
        body_hash,
    ])
    credential_scope = f"{datestamp}/{region}/{service}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256",
        amzdate,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _hmac(sk.encode("utf-8"), datestamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Host": host,
        "Content-Type": content_type,
        "X-Date": amzdate,
        "X-Content-Sha256": body_hash,
        "Authorization": authorization,
    }


# ---------------------------------------------------------------------------
# OpenAPI 客户端
# ---------------------------------------------------------------------------

@dataclass
class VeApiClient:
    access_key: str
    secret_key: str
    region: str = DEFAULT_REGION
    host: str = VEFAAS_HOST
    timeout: float = 60.0
    dry_run: bool = False

    def call(self, *, service: str, action: str, version: str,
             body: dict, http_method: str = "POST") -> dict:
        query = {"Action": action, "Version": version}
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = _sign_volc_v4(
            self.access_key, self.secret_key, service, self.region, self.host,
            http_method, query, body_bytes,
        )
        url = f"https://{self.host}/?{urllib.parse.urlencode(query)}"
        _log.info("[%s] %s %s body=%d bytes", service, http_method, action, len(body_bytes))
        if self.dry_run:
            print(f"\n--- DRY-RUN {service}.{action} ---")
            print(json.dumps(body, indent=2, ensure_ascii=False))
            return {"_dry_run": True}

        req = urllib.request.Request(url, data=body_bytes, headers=headers,
                                     method=http_method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAPI {action} failed: HTTP {e.code}: {err_body}"
            ) from None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"non-JSON response: {raw[:512]!r}") from None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

@dataclass
class DeployConfig:
    access_key: str
    secret_key: str
    region: str
    app_name: str              # vefaas function name (no underscore!)
    image_repo: str            # cr-cn-beijing.volces.com/<namespace>/<repo>
    image_tag: str
    cpu: float = DEFAULT_CPU
    memory_mb: int = DEFAULT_MEMORY_MB
    timeout_secs: int = DEFAULT_TIMEOUT_SECS
    envs: dict[str, str] = field(default_factory=dict)
    nas_mounts: list[dict] = field(default_factory=list)   # [{nas_id, mount, remote}]
    tos_mounts: list[dict] = field(default_factory=list)   # [{bucket, mount, prefix}]
    apig_instance_name: str = ""
    apig_service_name: str = ""
    apig_upstream_name: str = ""

    @property
    def full_image(self) -> str:
        return f"{self.image_repo}:{self.image_tag}"

    @classmethod
    def from_args_and_env(cls, args: argparse.Namespace) -> "DeployConfig":
        # 1) 尝试读 config.yaml (可选)
        cfg_yaml: dict[str, Any] = {}
        if args.config and pathlib.Path(args.config).exists():
            try:
                import yaml  # type: ignore
                cfg_yaml = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8")) or {}
            except ImportError:
                _log.warning("PyYAML not installed; ignoring %s", args.config)

        v = cfg_yaml.get("volcengine", {}) or {}
        f = cfg_yaml.get("vefaas", {}) or {}
        a = cfg_yaml.get("veapig", {}) or {}

        ak = (args.access_key
              or v.get("access_key")
              or os.environ.get("VOLC_ACCESS_KEY")
              or os.environ.get("VOLC_AK")
              or "")
        sk = (args.secret_key
              or v.get("secret_key")
              or os.environ.get("VOLC_SECRET_KEY")
              or os.environ.get("VOLC_SK")
              or "")
        if not ak or not sk:
            raise SystemExit(
                "Missing VOLC_ACCESS_KEY / VOLC_SECRET_KEY (CLI / env / config.yaml)"
            )

        region = args.region or v.get("region") or DEFAULT_REGION
        app_name = (args.app_name or f.get("app_name") or "xyq-manju").replace("_", "-")
        image_repo = (args.image_repo or f.get("image_repo")
                      or f"cr-{region}.volces.com/xyq/manju")
        image_tag = args.image_tag or f.get("image_tag") or "latest"
        cpu = float(args.cpu or f.get("cpu") or DEFAULT_CPU)
        memory_mb = int(args.memory_mb or f.get("memory_mb") or DEFAULT_MEMORY_MB)
        timeout_secs = int(args.timeout or f.get("timeout_secs") or DEFAULT_TIMEOUT_SECS)

        # env 注入: 默认从 .env 取已验证 keys (与 sync_keys_to_windows 一致)
        envs = dict(f.get("envs", {}) or {})
        env_passthrough = [
            # 国产核心
            "VOLC_ACCESS_KEY", "VOLC_SECRET_KEY", "VOLC_ARK_API_KEY",
            "ARK_API_KEY", "DOUBAO_API_KEY", "DOUBAO_ENDPOINT_ID", "DOUBAO_MODEL",
            "DOUBAO_TTS_APPID", "DOUBAO_TTS_TOKEN", "DOUBAO_TTS_CLUSTER",
            "VOLC_REGION",
            # TOS / S3
            "TOS_BUCKET", "TOS_ENDPOINT", "TOS_REGION", "TOS_PUBLIC_BASE",
            "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET", "S3_ENDPOINT", "S3_REGION",
            # 阿里
            "DASHSCOPE_API_KEY", "TONGYI_API_KEY",
            # LLM Fallback
            "DEEPSEEK_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
            "MISTRAL_API_KEY", "GROQ_API_KEY", "XAI_API_KEY", "SPARK_API_KEY",
            # 兜底
            "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
            # 业务
            "JWT_SECRET", "INTERNAL_API_SECRET",
            "STORAGE_BACKEND", "CN_DOMESTIC_MODE", "LLM_PROVIDER_CHAIN",
            "TTS_PRIMARY", "IMAGE_GEN_PRIMARY", "SCHEMA_VALIDATOR",
            "MANJU_AGENT_MODE", "MANJU_AGENT_REQ_KEY",
            "MOCK_MODE", "USE_REAL_COVER", "USE_REAL_WAN_ANIMATE",
            "FORCE_MOCK_TTS_ELEVENLABS",
            "SITE_URL", "CORS_ORIGINS", "PUBLIC_URL",
            "LOG_LEVEL", "TZ",
        ]
        # 优先从 User 级 setx 读 (sync_keys_to_windows 写的真值); 进程级旧值兜底
        def _read_env(k: str) -> str:
            v = ""
            try:  # type: ignore[attr-defined]
                # Windows: 读 HKCU\Environment 拿 setx 真值, 绕开父进程 snapshot
                import ctypes
                if os.name == "nt":
                    import winreg  # type: ignore
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                        try:
                            v, _ = winreg.QueryValueEx(h, k)
                        except FileNotFoundError:
                            v = ""
            except Exception:  # noqa: BLE001
                v = ""
            return v or os.environ.get(k, "") or ""

        for k in env_passthrough:
            val = _read_env(k)
            if val and not _is_placeholder(val) and k not in envs:
                envs[k] = val
        envs.setdefault("TZ", "Asia/Shanghai")
        envs.setdefault("LOG_LEVEL", "INFO")
        envs.setdefault("STORAGE_BACKEND", "tos")
        envs.setdefault("EMBEDDED_WORKER", "1")

        # NAS / TOS 挂载 (可选)
        nas_mounts = f.get("nas_mounts", []) or []
        tos_mounts = f.get("tos_mounts", []) or []
        if not tos_mounts and envs.get("TOS_BUCKET"):
            # 默认把 TOS bucket 也挂到 /mnt/tos 做兜底 (可选)
            tos_mounts = [{
                "bucket": envs["TOS_BUCKET"],
                "mount": "/mnt/tos",
                "prefix": "vefaas/",
            }]

        apig_instance = args.apig_instance or a.get("instance_name") or ""
        apig_service = args.apig_service or a.get("service_name") or ""
        apig_upstream = args.apig_upstream or a.get("upstream_name") or ""

        return cls(
            access_key=ak, secret_key=sk, region=region,
            app_name=app_name, image_repo=image_repo, image_tag=image_tag,
            cpu=cpu, memory_mb=memory_mb, timeout_secs=timeout_secs,
            envs=envs, nas_mounts=nas_mounts, tos_mounts=tos_mounts,
            apig_instance_name=apig_instance, apig_service_name=apig_service,
            apig_upstream_name=apig_upstream,
        )


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_build(cfg: DeployConfig, *, dry_run: bool) -> None:
    """docker build & push."""
    dockerfile = _REPO_ROOT / "deploy" / "cn-volc-vefaas" / "Dockerfile.vefaas"
    if not dockerfile.exists():
        raise SystemExit(f"Dockerfile not found: {dockerfile}")
    image = cfg.full_image
    build_cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "-t", image,
        "--platform", "linux/amd64",
        str(_REPO_ROOT),
    ]
    print("[build]", " ".join(build_cmd))
    if not dry_run:
        subprocess.run(build_cmd, check=True)


def step_push(cfg: DeployConfig, *, dry_run: bool) -> None:
    push_cmd = ["docker", "push", cfg.full_image]
    print("[push]", " ".join(push_cmd))
    if not dry_run:
        subprocess.run(push_cmd, check=True)


def build_create_function_payload(cfg: DeployConfig) -> dict:
    """构造 CreateFunction OpenAPI payload."""
    return {
        "Name": cfg.app_name,
        "Description": "AI 漫剧 - 火山引擎 veFaaS 单容器部署 (v9)",
        "Runtime": DEFAULT_RUNTIME,
        "Source": cfg.full_image,
        "SourceType": "image",
        "Command": "/app/run.sh",
        "Port": 8000,
        "CpuStrategy": "guaranteed",
        "MemoryMB": cfg.memory_mb,
        "RequestTimeout": cfg.timeout_secs,
        "InitializerSec": DEFAULT_INITIALIZER_SECS,
        # veFaaS 模型语义 (经实测 API 错误信息确认):
        #   ExclusiveMode=true  → MaxConcurrency 必须 = 1 (单实例独占, 1 req-at-a-time)
        #   ExclusiveMode=false → MaxConcurrency 必须 = 0 (容器内部线程池处理并发,
        #                                                  veFaaS 按需扩容 replica)
        # web service 走 ExclusiveMode=false: Caddy + uvicorn 自己负责高并发,
        # veFaaS 看流量增加时自动扩 replica (MinReplicas..MaxReplicas).
        "ExclusiveMode": False,
        "MaxConcurrency": 0,
        "MinReplicas": 0,
        "MaxReplicas": 10,
        "Envs": [
            {"Key": k, "Value": str(v)} for k, v in cfg.envs.items()
        ],
        "NasStorage": {
            "NasConfigs": [
                {
                    "NasId":      m.get("nas_id"),
                    "MountPoint": m.get("mount", "/mnt/nas"),
                    "RemotePath": m.get("remote", "/"),
                }
                for m in cfg.nas_mounts
                if m.get("nas_id")
            ],
        } if cfg.nas_mounts else None,
        "TosMountConfig": {
            "TosMountPoints": [
                {
                    "Bucket":     m["bucket"],
                    "MountPoint": m.get("mount", "/mnt/tos"),
                    "Prefix":     m.get("prefix", ""),
                    "ReadOnly":   False,
                }
                for m in cfg.tos_mounts
            ],
        } if cfg.tos_mounts else None,
    }


def step_create_or_update_function(client: VeApiClient, cfg: DeployConfig) -> str:
    """优先 CreateFunction; 若 already exists 改 UpdateFunction."""
    payload = build_create_function_payload(cfg)
    # 清理 None 字段, 让 OpenAPI 不收无效字段
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        resp = client.call(
            service=VEFAAS_SERVICE, action="CreateFunction",
            version=VEFAAS_VERSION, body=payload,
        )
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        fid = result.get("Id") or result.get("FunctionId") or result.get("_dry_run")
        print(f"[function] CreateFunction OK id={fid}")
        return str(fid)
    except RuntimeError as e:
        msg = str(e)
        if "AlreadyExists" in msg or "exists" in msg.lower() or "Duplicate" in msg:
            print("[function] Already exists, calling UpdateFunction")
            upd_payload = dict(payload)
            upd_payload["Id"] = cfg.app_name  # veFaaS UpdateFunction by name/id
            resp = client.call(
                service=VEFAAS_SERVICE, action="UpdateFunction",
                version=VEFAAS_VERSION, body=upd_payload,
            )
            return cfg.app_name
        raise


def step_release_function(client: VeApiClient, fid: str) -> None:
    """发布新版本."""
    body = {"FunctionId": fid, "Description": f"deploy at {_utc_iso()}"}
    resp = client.call(
        service=VEFAAS_SERVICE, action="CreateRelease",
        version=VEFAAS_VERSION, body=body,
    )
    rel_id = (resp or {}).get("Result", {}).get("Id", "?")
    print(f"[release] CreateRelease OK release_id={rel_id}")


def step_create_apig_route(client: VeApiClient, cfg: DeployConfig, fid: str) -> str | None:
    """创建 API 网关路由, 返回公网域名 (可选)."""
    if not (cfg.apig_instance_name and cfg.apig_service_name and cfg.apig_upstream_name):
        print("[apig] skipped (no instance/service/upstream configured)")
        return None
    body = {
        "InstanceName": cfg.apig_instance_name,
        "ServiceName": cfg.apig_service_name,
        "UpstreamName": cfg.apig_upstream_name,
        "BackendType": "vefaas",
        "BackendId": fid,
        "Path": "/",
        "MatchType": "prefix",
        "Methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    }
    resp = client.call(
        service=VEAPIG_SERVICE, action="CreateRoute", version="2022-11-12", body=body,
    )
    domain = (resp or {}).get("Result", {}).get("Domain", "")
    if domain:
        print(f"[apig] route created, domain=https://{domain}")
    return domain or None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy XYQ Manju to Volcengine veFaaS")
    parser.add_argument("--config", default="deploy/cn-volc-vefaas/config.yaml",
                        help="optional YAML config (overrides env / defaults)")
    parser.add_argument("--access-key", default="")
    parser.add_argument("--secret-key", default="")
    parser.add_argument("--region", default="")
    parser.add_argument("--app-name", default="",
                        help="veFaaS function name (no underscore!)")
    parser.add_argument("--image-repo", default="")
    parser.add_argument("--image-tag", default="")
    parser.add_argument("--cpu", type=float, default=None)
    parser.add_argument("--memory-mb", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--apig-instance", default="")
    parser.add_argument("--apig-service", default="")
    parser.add_argument("--apig-upstream", default="")
    parser.add_argument("--build", action="store_true",
                        help="run docker build before deploy")
    parser.add_argument("--push", action="store_true",
                        help="run docker push before deploy")
    parser.add_argument("--no-release", action="store_true",
                        help="skip CreateRelease")
    parser.add_argument("--dry-run", action="store_true",
                        help="print OpenAPI payloads, don't call")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = DeployConfig.from_args_and_env(args)
    print(f"[config] app_name={cfg.app_name} region={cfg.region}")
    print(f"[config] image={cfg.full_image}  cpu={cfg.cpu} mem={cfg.memory_mb}MB")
    print(f"[config] envs={len(cfg.envs)} passthrough  nas={len(cfg.nas_mounts)}  tos={len(cfg.tos_mounts)}")

    if args.build:
        step_build(cfg, dry_run=args.dry_run)
    if args.push:
        step_push(cfg, dry_run=args.dry_run)

    client = VeApiClient(
        access_key=cfg.access_key, secret_key=cfg.secret_key,
        region=cfg.region, dry_run=args.dry_run,
    )

    fid = step_create_or_update_function(client, cfg)
    if not args.no_release:
        step_release_function(client, fid)
    domain = step_create_apig_route(client, cfg, fid)

    print("")
    print("=" * 60)
    print(" veFaaS Deploy 完成")
    print("=" * 60)
    print(f"  Function ID: {fid}")
    print(f"  Image:       {cfg.full_image}")
    print(f"  Region:      {cfg.region}")
    print(f"  App Name:    {cfg.app_name}")
    if domain:
        print(f"  Public URL:  https://{domain}/api/health")
    print()
    print("下一步:")
    print("  1. 浏览器开 https://console.volcengine.com/vefaas 查看函数状态")
    print("  2. 若已配 API 网关, curl 上面 Public URL 验证 200")
    print("  3. 跑 scripts/verify_volc_chain.py 做生产 smoke")
    return 0


if __name__ == "__main__":
    sys.exit(main())
