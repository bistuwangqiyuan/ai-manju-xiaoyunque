"""Direct upload of web/out to Tencent CloudBase static hosting bucket.

Bypasses the broken `tcb hosting deploy` / MCP-multi-file path. Uses local
TENCENT_SECRET_ID / TENCENT_SECRET_KEY env vars (or the TENCENTCLOUD_*
variants) plus the cos-python-sdk-v5 client.

Bucket: 79d2-static-cursoraicode-5g67ezfl8a1891da-1300352403 (ap-shanghai)
"""
from __future__ import annotations

import mimetypes
import os
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from qcloud_cos import CosConfig, CosS3Client

ROOT = pathlib.Path(r"D:\project\cursor\dev\ai-manju-xiaoyunque\web\out")
BUCKET = "79d2-static-cursoraicode-5g67ezfl8a1891da-1300352403"
REGION = "ap-shanghai"
MAX_WORKERS = 8


def _get_creds() -> tuple[str, str]:
    sid = os.environ.get("TENCENTCLOUD_SECRET_ID") or os.environ.get("TENCENT_SECRET_ID")
    skey = os.environ.get("TENCENTCLOUD_SECRET_KEY") or os.environ.get("TENCENT_SECRET_KEY")
    if not sid or not sid.startswith("AKID"):
        raise SystemExit(
            "Missing/invalid Tencent Cloud AK (expected AKID...). "
            "Set TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY env vars."
        )
    if not skey:
        raise SystemExit("Missing TENCENTCLOUD_SECRET_KEY env var")
    return sid, skey


def _content_type(p: pathlib.Path) -> str:
    ct, _ = mimetypes.guess_type(p.name)
    if ct:
        return ct
    if p.suffix == ".html":
        return "text/html; charset=utf-8"
    if p.suffix == ".css":
        return "text/css; charset=utf-8"
    if p.suffix == ".js":
        return "application/javascript; charset=utf-8"
    if p.suffix == ".json":
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def _upload_one(client: CosS3Client, p: pathlib.Path) -> tuple[str, bool, str]:
    key = p.relative_to(ROOT).as_posix()
    try:
        client.upload_file(
            Bucket=BUCKET,
            LocalFilePath=str(p),
            Key=key,
            EnableMD5=False,
            MAXThread=4,
            ContentType=_content_type(p),
        )
        return key, True, ""
    except Exception as exc:  # noqa: BLE001
        return key, False, repr(exc)


def main() -> int:
    sid, skey = _get_creds()
    cfg = CosConfig(Region=REGION, SecretId=sid, SecretKey=skey, Timeout=120)
    client = CosS3Client(cfg)

    files = sorted(p for p in ROOT.rglob("*") if p.is_file())
    print(f"Uploading {len(files)} files to bucket={BUCKET} region={REGION}")

    ok = 0
    fail = 0
    fail_keys: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(_upload_one, client, p) for p in files]
        for i, fut in enumerate(as_completed(futs), 1):
            key, success, err = fut.result()
            tag = "OK" if success else "FAIL"
            print(f"[{i:>3}/{len(files):>3}] {tag} {key}")
            if success:
                ok += 1
            else:
                fail += 1
                fail_keys.append((key, err))

    print()
    print(f"Done. ok={ok} fail={fail}")
    if fail_keys:
        print("Failures:")
        for k, e in fail_keys[:20]:
            print(f"  - {k}: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
