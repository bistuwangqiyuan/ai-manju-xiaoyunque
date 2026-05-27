"""Deploy FastAPI backend as CloudBase HTTP cloud function on BaaS env."""
from __future__ import annotations

import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"
FN_ROOT = REPO / "cloudfunctions" / "xyq-api"
WEB = REPO / "web"
OUT = WEB / "out"

COPY_DIRS = ["backend/app", "src", "config", "prompts", "tools", "compliance"]
COPY_AS = {"backend/app": "app"}


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


def _run(cmd: str, *, env: dict[str, str] | None = None, cwd: pathlib.Path | None = None) -> int:
    print(f"\n>>> {cmd[:160]}")
    return subprocess.run(cmd, shell=True, cwd=str(cwd or REPO), env=env, text=True).returncode


def write_scf_bootstrap() -> None:
    """Write scf_bootstrap with LF endings (CRLF breaks Linux exec)."""
    content = (
        "#!/bin/bash\n"
        "export PYTHONPATH=\"./third_party:$(pwd):$PYTHONPATH\"\n"
        "export MOCK_MODE=1\n"
        "export EMBEDDED_WORKER=1\n"
        "export DATABASE_URL=sqlite:////tmp/xyq.db\n"
        "export STORAGE_DIR=/tmp/storage\n"
        "export CORS_ORIGINS=*\n"
        "exec /var/lang/python39/bin/python3.9 -m uvicorn app.main:app --host 0.0.0.0 --port 9000\n"
    )
    (FN_ROOT / "scf_bootstrap").write_bytes(content.encode("utf-8"))


def stage_function_code() -> None:
    """Copy backend + pipeline into cloudfunctions/xyq-api (keep index.py)."""
    write_scf_bootstrap()
    for rel in COPY_DIRS:
        src = REPO / rel
        dest_name = COPY_AS.get(rel, rel.split("/")[-1])
        dest = FN_ROOT / dest_name
        if dest.exists():
            shutil.rmtree(dest)
        if src.is_dir():
            shutil.copytree(
                src,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )
            print(f"staged {rel} -> {dest.relative_to(REPO)}")


def build_frontend(api_base: str) -> int:
    env = os.environ.copy()
    env["CLOUDBASE_STATIC"] = "1"
    env["NEXT_PUBLIC_BACKEND_URL"] = api_base.rstrip("/")
    if _run("npm ci --no-audit --no-fund", cwd=WEB, env=env) != 0:
        return 1
    return _run("npm run build", cwd=WEB, env=env)


def main() -> int:
    cfg = _load_env()
    baas_env = cfg.get("ENV_ID", "")
    if not baas_env or not cfg.get("TENCENT_SECRET_ID"):
        print("Missing ENV_ID / credentials", file=sys.stderr)
        return 2

    # CloudBase HTTP 函数默认访问域名（部署后可在控制台确认）
    api_base = cfg.get("API_URL") or f"https://{baas_env}.ap-shanghai.app.tcloudbase.com"
    static_url = cfg.get("SITE_URL") or f"https://{baas_env}-1300352403.tcloudbaseapp.com"

    print("=== [1/4] Stage cloud function code ===")
    stage_function_code()

    print("=== [2/4] Deploy HTTP cloud function xyq-api ===")
    env = os.environ.copy()
    env.update(cfg)
    env["ENV_ID"] = baas_env
    _run(
        f'tcb login --apiKeyId {cfg["TENCENT_SECRET_ID"]} --apiKey {cfg["TENCENT_SECRET_KEY"]}',
        env=env,
    )
    baas_rc = REPO / "cloudbaserc.baas.json"
    main_rc = REPO / "cloudbaserc.json"
    rc_backup = REPO / "cloudbaserc.json.bak"
    if baas_rc.exists():
        if main_rc.exists():
            shutil.copy2(main_rc, rc_backup)
        shutil.copy2(baas_rc, main_rc)
    rc_fn = _run(
        f'tcb fn deploy xyq-api --env-id {baas_env} --httpFn --path /api '
        f'--dir cloudfunctions/xyq-api --force --runtime Python3.9',
        env=env,
    )
    if rc_backup.exists():
        shutil.copy2(rc_backup, main_rc)
        rc_backup.unlink(missing_ok=True)
    if rc_fn != 0:
        return rc_fn

    print("=== [3/4] Build + deploy static frontend ===")
    if build_frontend(api_base) != 0:
        return 1
    rc_host = _run(f'tcb hosting deploy "{OUT}" / --env-id {baas_env}', env=env)

    print("\n=== Deploy summary ===")
    print(f"Frontend:  {static_url}")
    print(f"API base:  {api_base}/api")
    print(f"Guide:     {static_url}/guide/")
    print(f"Showcase:  {static_url}/showcase/")
    print(f"Health:    {api_base}/api/health")
    return 0 if rc_host == 0 else rc_host


if __name__ == "__main__":
    sys.exit(main())
