"""Probe CloudRun status on target envs."""
from __future__ import annotations

import json
import re
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.tcbr.v20220217 import tcbr_client, models

ENV_SIMPLE = Path(__file__).resolve().parents[1] / "deploy" / "cn-serverless" / ".env.simple"


def _load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            v = m.group(2).strip().strip('"').strip("'")
            if v:
                out[m.group(1)] = v
    return out


def main() -> None:
    cfg = _load_env()
    client = tcbr_client.TcbrClient(
        credential.Credential(cfg["TENCENT_SECRET_ID"], cfg["TENCENT_SECRET_KEY"]),
        "ap-shanghai",
    )
    for env in [cfg.get("CLOUDRUN_ENV_ID"), cfg.get("ENV_ID")]:
        if not env:
            continue
        print(f"\n=== DescribeCloudRunServers env={env} ===")
        req = models.DescribeCloudRunServersRequest()
        req.EnvId = env
        req.Offset = 0
        req.Limit = 20
        try:
            resp = client.DescribeCloudRunServers(req)
            print(json.dumps(json.loads(resp.to_json_string()), indent=2)[:4000])
        except Exception as exc:
            print("ERR:", exc)

        print(f"\n=== DescribeCloudRunServerDetail env={env} server=xyq ===")
        dreq = models.DescribeCloudRunServerDetailRequest()
        dreq.EnvId = env
        dreq.ServerName = "xyq"
        try:
            dresp = client.DescribeCloudRunServerDetail(dreq)
            print(json.dumps(json.loads(dresp.to_json_string()), indent=2)[:6000])
        except Exception as exc:
            print("ERR:", exc)


if __name__ == "__main__":
    main()
