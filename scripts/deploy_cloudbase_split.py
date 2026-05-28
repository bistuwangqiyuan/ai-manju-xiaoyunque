"""Split deploy: static frontend on BaaS env + CloudRun API backend.

Frontend URL (BaaS static hosting):
  https://{ENV_ID}-{appid}.tcloudbaseapp.com

Backend URL (CloudRun on linked run env):
  https://xyq-{appid}.sh.run.tcloudbase.com
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"
WEB = REPO / "web"
OUT = WEB / "out"


def _load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_SIMPLE.exists():
        for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if m:
                v = m.group(2).strip().strip('"').strip("'")
                if v:
                    out[m.group(1)] = v
    return out


def _run(
    cmd: str,
    *,
    env: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
    input_text: str = "",
) -> int:
    print(f"\n>>> {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    return subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd or REPO),
        env=env,
        text=True,
        input=input_text or None,
    ).returncode


def _backend_url(cfg: dict[str, str]) -> str:
    api = cfg.get("API_URL", "").strip()
    if api:
        return api.rstrip("/")
    explicit = cfg.get("SITE_URL", "").strip()
    if explicit and explicit != "https://placeholder":
        return explicit.rstrip("/")
    # default CloudRun domain for service xyq
    return "https://xyq-262646-8-1300352403.sh.run.tcloudbase.com"


def build_static_frontend(backend_url: str) -> int:
    env = os.environ.copy()
    env["CLOUDBASE_STATIC"] = "1"
    env["NEXT_PUBLIC_BACKEND_URL"] = backend_url
    if _run("npm ci --no-audit --no-fund", cwd=WEB, env=env) != 0:
        return 1
    return _run("npm run build", cwd=WEB, env=env)


def deploy_hosting(baas_env: str, cfg: dict[str, str]) -> int:
    env = os.environ.copy()
    env.update(cfg)
    env["ENV_ID"] = baas_env
    _run(f'tcb login --apiKeyId {cfg["TENCENT_SECRET_ID"]} --apiKey {cfg["TENCENT_SECRET_KEY"]}', env=env)
    if not OUT.is_dir():
        print(f"Missing {OUT} — run build first", file=sys.stderr)
        return 2
    return _run(f'tcb hosting deploy "{OUT}" / --env-id {baas_env}', env=env)


def deploy_backend_cloudrun(run_env: str, cfg: dict[str, str], *, env_params: dict) -> int:
    """Deploy backend container via tcb CLI + inject env via API."""
    env = os.environ.copy()
    env.update(cfg)
    env["ENV_ID"] = run_env
    dockerfile = REPO / "deploy" / "cn-serverless" / "Dockerfile.serverless"
    (REPO / "Dockerfile").write_bytes(dockerfile.read_bytes())

    code = _run(
        f'tcb cloudrun deploy --env-id {run_env} -s xyq --port 8000 --source . --force',
        env=env,
        cwd=REPO,
        input_text="\n",
    )

    try:
        from tencentcloud.common import credential
        from tencentcloud.tcbr.v20220217 import tcbr_client, models

        client = tcbr_client.TcbrClient(
            credential.Credential(cfg["TENCENT_SECRET_ID"], cfg["TENCENT_SECRET_KEY"]),
            "ap-shanghai",
        )
        req = models.UpdateCloudRunServerRequest()
        req.EnvId = run_env
        req.ServerName = "xyq"
        req.ServerConfig = models.ServerBaseConfig()
        req.ServerConfig.EnvParams = json.dumps(env_params, ensure_ascii=False)
        req.ServerConfig.Port = 8000
        req.ServerConfig.MinNum = 1
        req.ServerConfig.MaxNum = 5
        req.ServerConfig.Cpu = 1
        req.ServerConfig.Mem = 2
        client.UpdateCloudRunServer(req)
        print("Updated xyq runtime env params")
    except Exception as exc:
        print(f"warn: env params update: {exc}", file=sys.stderr)
    return code


def main() -> int:
    cfg = _load_env()
    baas_env = cfg.get("ENV_ID", "")
    run_env = cfg.get("CLOUDRUN_ENV_ID") or baas_env
    if not baas_env or not cfg.get("TENCENT_SECRET_ID"):
        print("Missing ENV_ID / credentials in .env.simple", file=sys.stderr)
        return 2

    backend_url = _backend_url(cfg)
    print(f"BaaS env (frontend): {baas_env}")
    print(f"Run env (backend):     {run_env}")
    print(f"Backend URL:           {backend_url}")

    if _run("python scripts/sync_sample_assets.py") != 0:
        return 1

    if build_static_frontend(backend_url) != 0:
        return 1

    env_params = {
        "JWT_SECRET": cfg.get("JWT_SECRET", "change-me-in-production"),
        "INTERNAL_API_SECRET": cfg.get("INTERNAL_API_SECRET", "change-me-in-production"),
        "DATABASE_URL": "sqlite:////tmp/xyq.db",
        "STORAGE_DIR": "/tmp/storage",
        "EMBEDDED_WORKER": "1",
        "CORS_ORIGINS": "*",
        "PORT": "8000",
        "MOCK_MODE": cfg.get("MOCK_MODE", "0"),
        "TZ": "Asia/Shanghai",
        "LOG_LEVEL": "INFO",
    }

    rc_back = deploy_backend_cloudrun(run_env, cfg, env_params=env_params)
    rc_front = deploy_hosting(baas_env, cfg)

    static_url = f"https://{baas_env}-1300352403.tcloudbaseapp.com"
    print("\n=== Deploy summary ===")
    print(f"Frontend (static): {static_url}")
    print(f"Backend (API):     {backend_url}")
    print(f"User guide:        {static_url}/guide/")
    return 0 if rc_front == 0 else rc_front


if __name__ == "__main__":
    sys.exit(main())
