"""部署 deploy/cloudfn-slim 到 CloudBase SCF，并推送真实管线环境变量。

从环境变量读取密钥（勿写入 git）：
  VOLC_ACCESS_KEY / VOLC_SECRET_KEY
  HAPPYHORSE_API_KEY 或 DASHSCOPE_API_KEY
  TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY（可选，SCF 运行时也会自动注入）

用法（PowerShell）：
  $env:VOLC_ACCESS_KEY='...'
  $env:VOLC_SECRET_KEY='...'
  $env:HAPPYHORSE_API_KEY='sk-...'
  python scripts/deploy_cloudfn_slim.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLIM = ROOT / "deploy" / "cloudfn-slim"
ENV_ID = "cursoraicode-5g67ezfl8a1891da"
FN = "xyq-api"


def _must(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if not v:
        print(f"FAIL: 缺少环境变量 {name}")
        sys.exit(1)
    return v


def main() -> int:
    volc_ak = _must("VOLC_ACCESS_KEY")
    volc_sk = _must("VOLC_SECRET_KEY")
    hh_key = (
        os.environ.get("HAPPYHORSE_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or ""
    ).strip()
    if not hh_key:
        print("WARN: 未设置 HAPPYHORSE_API_KEY — 限流时无法切换 HappyHorse 备用")

    base_rc = json.loads((SLIM / "cloudbaserc.json").read_text(encoding="utf-8"))
    fn_cfg = base_rc["functions"][0]
    fn_cfg["envVariables"] = {
        "REAL_VIDEO_MODE": "manju",
        "COS_BUCKET": "6375-cursoraicode-5g67ezfl8a1891da-1300352403",
        "COS_REGION": "ap-shanghai",
        "CORS_ORIGINS": "*",
        "DATABASE_URL": "sqlite:////tmp/xyq.db",
        "EMBEDDED_WORKER": "0",
        "STORAGE_DIR": "/tmp/storage",
        "VOLC_ACCESS_KEY": volc_ak,
        "VOLC_SECRET_KEY": volc_sk,
        "HAPPYHORSE_API_KEY": hh_key,
        "DASHSCOPE_API_KEY": hh_key,
    }
    fn_cfg["timeout"] = 120
    fn_cfg["memorySize"] = 512

    rc_path = SLIM / "cloudbaserc.json"
    rc_path.write_text(json.dumps(base_rc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {rc_path} (含密钥，请勿 git commit)")

    cmds = [
        ["tcb", "config", "update", "fn", FN, "-e", ENV_ID],
        ["tcb", "fn", "code", "update", FN, "--dir", str(SLIM), "-e", ENV_ID],
    ]
    for cmd in cmds:
        print(f"\n>>> {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=str(ROOT), check=False)
        if r.returncode != 0:
            print(f"FAIL: exit {r.returncode}")
            return r.returncode

    print("\nDone. 验证: curl <backend>/api/health → real_video_mode=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
