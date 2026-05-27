"""Build static web + deploy single-container bundle to CloudBase CloudRun."""
from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import secrets
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


def _run(cmd: str, *, env: dict[str, str] | None = None, cwd: pathlib.Path | None = None, input_text: str = "") -> int:
    print(f"\n>>> {cmd[:140]}")
    return subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd or REPO),
        env=env,
        text=True,
        input=input_text or None,
    ).returncode


def build_frontend() -> int:
    env = os.environ.copy()
    env["CLOUDBASE_STATIC"] = "1"
    env["NEXT_PUBLIC_BACKEND_URL"] = ""
    if _run("npm ci --no-audit --no-fund", cwd=WEB, env=env) != 0:
        return 1
    return _run("npm run build", cwd=WEB, env=env)


def main() -> int:
    cfg = _load_env()
    env = os.environ.copy()
    env.update(cfg)
    env.setdefault("JWT_SECRET", base64.b64encode(secrets.token_bytes(48)).decode())
    env.setdefault("INTERNAL_API_SECRET", base64.b64encode(secrets.token_bytes(48)).decode())
    env.setdefault("MOCK_MODE", "1")

    deploy_env = env.get("CLOUDRUN_ENV_ID") or env.get("ENV_ID", "")
    if not deploy_env or not cfg.get("TENCENT_SECRET_ID"):
        print("Missing credentials in .env.simple", file=sys.stderr)
        return 2

    print("=== [1/4] Build static frontend (same-origin API) ===")
    if build_frontend() != 0:
        return 1
    if not OUT.is_dir():
        print(f"Missing {OUT}", file=sys.stderr)
        return 1
    samples = OUT / "samples"
    print(f"Static build OK — samples dir: {samples.is_dir()}, files: {len(list(samples.glob('*'))) if samples.is_dir() else 0}")

    print("=== [2/4] Prepare Dockerfile.cloudbase ===")
    dockerfile = REPO / "deploy" / "cn-serverless" / "Dockerfile.cloudbase"
    (REPO / "Dockerfile").write_bytes(dockerfile.read_bytes())

    print("=== [3/4] tcb login + cloudrun deploy ===")
    env["ENV_ID"] = deploy_env
    _run("tcb logout", env=env)
    if _run(f'tcb login --apiKeyId {cfg["TENCENT_SECRET_ID"]} --apiKey {cfg["TENCENT_SECRET_KEY"]}', env=env) != 0:
        return 1

    code = _run(
        f'tcb cloudrun deploy --env-id {deploy_env} -s xyq --port 8080 --source . --force',
        env=env,
        input_text="\n",
    )

    print("=== [4/4] Inject runtime env ===")
    env_params = json.dumps({
        "JWT_SECRET": env["JWT_SECRET"],
        "INTERNAL_API_SECRET": env["INTERNAL_API_SECRET"],
        "DATABASE_URL": "sqlite:////data/xyq.db",
        "STORAGE_DIR": "/data/storage",
        "STATIC_WEB_DIR": "/app/static_web",
        "EMBEDDED_WORKER": "1",
        "MOCK_MODE": env.get("MOCK_MODE", "1"),
        "CORS_ORIGINS": "*",
        "PORT": "8080",
        "TZ": "Asia/Shanghai",
        "LOG_LEVEL": "INFO",
    }, ensure_ascii=False)

    try:
        from tencentcloud.common import credential
        from tencentcloud.tcbr.v20220217 import tcbr_client, models

        client = tcbr_client.TcbrClient(
            credential.Credential(cfg["TENCENT_SECRET_ID"], cfg["TENCENT_SECRET_KEY"]),
            "ap-shanghai",
        )
        req = models.UpdateCloudRunServerRequest()
        req.EnvId = deploy_env
        req.ServerName = "xyq"
        req.ServerConfig = models.ServerBaseConfig()
        req.ServerConfig.EnvParams = env_params
        req.ServerConfig.Port = 8080
        req.ServerConfig.MinNum = 1
        req.ServerConfig.MaxNum = 5
        req.ServerConfig.Cpu = 1
        req.ServerConfig.Mem = 2
        client.UpdateCloudRunServer(req)
        print("Runtime env updated")
    except Exception as exc:
        print(f"warn: env update: {exc}", file=sys.stderr)

    url = cfg.get("API_URL") or "https://xyq-262646-8-1300352403.sh.run.tcloudbase.com"
    print(f"\nDeploy submitted. Public URL: {url}")
    print(f"Guide:    {url}/guide/")
    print(f"Showcase: {url}/showcase/")
    return code


if __name__ == "__main__":
    sys.exit(main())
