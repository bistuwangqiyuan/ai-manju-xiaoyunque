"""Enable CloudBase Run (云托管) on an existing BaaS env."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.tcbr.v20220217 import tcbr_client

REPO = Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"


def _load_creds() -> tuple[str, str]:
    for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*(TENCENT_SECRET_ID|TENCENT_SECRET_KEY)=(.*)$", line)
        if m:
            globals()[m.group(1)] = m.group(2).strip()
    return globals()["TENCENT_SECRET_ID"], globals()["TENCENT_SECRET_KEY"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-id", required=True)
    ap.add_argument("--alias", default="manju")
    ap.add_argument("--region", default="ap-shanghai")
    args = ap.parse_args()
    sid, sk = _load_creds()
    client = tcbr_client.TcbrClient(credential.Credential(sid, sk), args.region)
    resp = client.call(
        "CreateCloudRunEnv",
        {
            "EnvId": args.env_id,
            "PackageType": "Standard",
            "Alias": args.alias,
            "Source": "cloud",
            "Channel": "cloud",
            "EnvType": "run",
        },
    )
    print(resp.decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
