#!/usr/bin/env python3
"""Create native SCF HTTP trigger (alternative to CloudBase HTTP access service)."""
from __future__ import annotations

import json
import pathlib
import re
import sys

from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"


def _load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def main() -> int:
    cfg = _load_env()
    env = cfg["ENV_ID"]
    client = scf_client.ScfClient(
        credential.Credential(cfg["TENCENT_SECRET_ID"], cfg["TENCENT_SECRET_KEY"]),
        "ap-shanghai",
    )
    desc = json.dumps(
        {
            "authRequired": False,
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        }
    )
    req = models.CreateTriggerRequest()
    req.FunctionName = "xyq-api"
    req.Namespace = env
    req.TriggerName = "http-api"
    req.Type = "http"
    req.TriggerDesc = desc
    try:
        resp = client.CreateTrigger(req)
        print("CreateTrigger OK:", resp.to_json_string())
    except Exception as exc:
        print("CreateTrigger failed:", exc, file=sys.stderr)

    greq = models.GetFunctionRequest()
    greq.FunctionName = "xyq-api"
    greq.Namespace = env
    fn = client.GetFunction(greq)
    print("Function Type:", fn.Type, "ProtocolType:", fn.ProtocolType)
    for t in fn.Triggers or []:
        print("Trigger:", t.to_json_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
