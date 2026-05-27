"""Deploy CloudRun service from a pre-built container image (skip remote build)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.tcbr.v20220217 import tcbr_client, models

REPO = Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"


def _load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            v = m.group(2).strip().strip('"').strip("'")
            if v:
                out[m.group(1)] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-id", default="")
    ap.add_argument("--service", default="xyq")
    ap.add_argument("--image", default="gcr.io/cloudrun/hello")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--wait", type=int, default=120)
    args = ap.parse_args()

    cfg = _load_env()
    env_id = args.env_id or cfg.get("CLOUDRUN_ENV_ID") or cfg["ENV_ID"]
    client = tcbr_client.TcbrClient(
        credential.Credential(cfg["TENCENT_SECRET_ID"], cfg["TENCENT_SECRET_KEY"]),
        "ap-shanghai",
    )

    env_params = {
        "EMBEDDED_WORKER": "1",
        "MOCK_MODE": "1",
        "DATABASE_URL": "sqlite:////tmp/xyq.db",
        "STORAGE_DIR": "/tmp/storage",
        "CORS_ORIGINS": "*",
        "JWT_SECRET": cfg.get("JWT_SECRET", "dev-secret-change-me"),
        "INTERNAL_API_SECRET": cfg.get("INTERNAL_API_SECRET", "dev-internal-change-me"),
        "PORT": str(args.port),
    }

    req = models.UpdateCloudRunServerRequest()
    req.EnvId = env_id
    req.ServerName = args.service
    req.ServerConfig = models.ServerBaseConfig()
    req.ServerConfig.Port = args.port
    req.ServerConfig.Cpu = 0.5
    req.ServerConfig.Mem = 1
    req.ServerConfig.MinNum = 1
    req.ServerConfig.MaxNum = 3
    req.ServerConfig.EnvParams = json.dumps(env_params, ensure_ascii=False)
    req.DeployInfo = models.DeployParam()
    req.DeployInfo.DeployType = "image"
    req.DeployInfo.ImageUrl = args.image
    req.DeployInfo.ReleaseType = "FULL"
    req.DeployInfo.DeployRemark = f"image deploy {args.image}"

    resp = client.UpdateCloudRunServer(req)
    print(resp.to_json_string())
    task_id = resp.TaskId

    deadline = time.time() + args.wait
    while time.time() < deadline:
        treq = models.DescribeServerManageTaskRequest()
        treq.EnvId = env_id
        treq.TaskId = task_id
        treq.ServerName = args.service
        task = client.DescribeServerManageTask(treq)
        print("task:", task.to_json_string()[:500])
        status = getattr(task, "Status", "") or ""
        if status.lower() in {"success", "finished", "done"}:
            return 0
        if status.lower() in {"failed", "error"}:
            return 1
        time.sleep(10)

    print("timeout waiting for task", task_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
