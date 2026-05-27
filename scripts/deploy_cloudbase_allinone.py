"""Deploy all-in-one container to CloudBase (wrapper for tcb framework deploy)."""
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


def _run(cmd: list[str], env: dict[str, str], *, input_text: str = "") -> int:
    print(f"\n>>> {' '.join(cmd[:6])}{'...' if len(cmd) > 6 else ''}")
    r = subprocess.run(
        cmd,
        env=env,
        cwd=str(REPO),
        shell=True,
        input=input_text or None,
        text=True,
    )
    return r.returncode


def main() -> int:
    cfg = _load_env()
    env = os.environ.copy()
    env.update(cfg)
    env.setdefault("JWT_SECRET", base64.b64encode(secrets.token_bytes(48)).decode())
    env.setdefault("INTERNAL_API_SECRET", base64.b64encode(secrets.token_bytes(48)).decode())
    env.setdefault("SITE_URL", "https://placeholder")
    env.setdefault("MOCK_MODE", "0")
    for k in ("VOLC_ARK_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "DOUBAO_API_KEY"):
        env.setdefault(k, "")

    deploy_env = env.get("CLOUDRUN_ENV_ID") or env.get("ENV_ID", "")
    if not deploy_env or not env.get("TENCENT_SECRET_ID") or not env.get("TENCENT_SECRET_KEY"):
        print("Missing ENV_ID / TENCENT_SECRET_ID / TENCENT_SECRET_KEY in .env.simple", file=sys.stderr)
        return 2
    print(f"Deploy target CloudRun env: {deploy_env}")
    env["ENV_ID"] = deploy_env  # tcb CLI prefers this over --env-id

    _run("tcb logout", env)
    code = _run(
        f'tcb login --apiKeyId {env["TENCENT_SECRET_ID"]} --apiKey {env["TENCENT_SECRET_KEY"]}',
        env,
    )
    if code != 0:
        return code

    dockerfile = REPO / "deploy" / "cn-serverless" / "Dockerfile.allinone"
    (REPO / "Dockerfile").write_bytes(dockerfile.read_bytes())
    print(f"Prepared {REPO / 'Dockerfile'} from Dockerfile.allinone")

    base_url = env.get("SITE_URL", "https://placeholder")
    if base_url == "https://placeholder":
        # filled after first deploy via verify script
        pass

    env_params = json.dumps({
        "JWT_SECRET": env["JWT_SECRET"],
        "INTERNAL_API_SECRET": env["INTERNAL_API_SECRET"],
        "DATABASE_URL": "sqlite:////data/xyq.db",
        "STORAGE_DIR": "/data/storage",
        "EMBEDDED_WORKER": "1",
        "CORS_ORIGINS": "*",
        "PORT": "8080",
        "MOCK_MODE": env.get("MOCK_MODE", "0"),
        "TZ": "Asia/Shanghai",
        "LOG_LEVEL": "INFO",
    }, ensure_ascii=False)

    # tcb 3.5 still prompts for gray deployment even with --force; default "No" = Enter
    code = _run(
        f'tcb cloudrun deploy --env-id {deploy_env} -s xyq --port 8080 '
        f'--source . --force',
        env,
        input_text="\n",
    )

    # inject runtime env vars (tcb deploy CLI does not read cloudbaserc envParams)
    try:
        from tencentcloud.common import credential
        from tencentcloud.tcbr.v20220217 import tcbr_client, models
        cred = credential.Credential(env["TENCENT_SECRET_ID"], env["TENCENT_SECRET_KEY"])
        client = tcbr_client.TcbrClient(cred, "ap-shanghai")
        req = models.UpdateCloudRunServerRequest()
        req.EnvId = deploy_env
        req.ServerName = "xyq"
        req.ServerConfig = models.ServerBaseConfig()
        req.ServerConfig.EnvParams = env_params
        req.ServerConfig.Port = 8080
        req.ServerConfig.MinNum = 0
        req.ServerConfig.MaxNum = 5
        req.ServerConfig.Cpu = 1
        req.ServerConfig.Mem = 2
        client.UpdateCloudRunServer(req)
        print("Updated xyq env params on CloudRun")
    except Exception as exc:
        print(f"warn: UpdateCloudRunServer env params: {exc}", file=sys.stderr)

    return code


if __name__ == "__main__":
    sys.exit(main())
