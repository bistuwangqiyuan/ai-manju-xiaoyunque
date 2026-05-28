#!/usr/bin/env python3
"""Verify live /samples/*.mp4 and /showcase on CloudBase static hosting."""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"
MIN_MP4_BYTES = 2_000_000


def _fetch(url: str, *, method: str = "GET", nbytes: int = 0) -> tuple[int, int, dict]:
    headers = {"Cache-Control": "no-cache", "User-Agent": "xyq-verify-samples/1.0"}
    if method == "GET" and nbytes > 0:
        headers["Range"] = f"bytes=0-{nbytes - 1}"
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read() if method == "GET" else b""
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, len(data), hdrs
    except Exception as exc:
        return 0, 0, {"error": str(exc)}


def main() -> int:
    catalog_path = REPO / "web" / "public" / "samples" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    checks: list[tuple[str, bool, str]] = []

    code, size, _ = _fetch(f"{BASE}/showcase/", nbytes=8192)
    checks.append(("GET /showcase/", code in (200, 206), f"status={code} read={size}"))

    _, _, html_hdrs = _fetch(f"{BASE}/showcase/")
    html_req = urllib.request.Request(
        f"{BASE}/showcase/",
        headers={"Cache-Control": "no-cache", "User-Agent": "xyq-verify-samples/1.0"},
    )
    with urllib.request.urlopen(html_req, timeout=45) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    has_gallery = any(k in html for k in ("官方", "作品", "showcase", "CommunityGallery"))
    checks.append(("showcase page content", has_gallery, f"html_len={len(html)}"))

    code, size, _ = _fetch(f"{BASE}/samples/catalog.json")
    checks.append(("GET /samples/catalog.json", code == 200, f"status={code} size={size}"))

    for sample in catalog["samples"]:
        video = sample["video_url"]
        url = BASE + video
        code, _, hdrs = _fetch(url, method="HEAD")
        length = int(hdrs.get("content-length", 0) or 0)
        if code == 200 and length < MIN_MP4_BYTES:
            code, read_len, _ = _fetch(url, nbytes=8192)
            length = max(length, read_len)
        ok = code == 200 and length >= MIN_MP4_BYTES
        checks.append((f"GET {video}", ok, f"status={code} bytes={length}"))

        cover = sample.get("cover_url")
        if cover:
            c_code, _, _ = _fetch(BASE + cover, method="HEAD")
            checks.append((f"GET {cover}", c_code == 200, f"status={c_code}"))

    passed = sum(1 for _, ok, _ in checks if ok)
    failed = sum(1 for _, ok, _ in checks if not ok)

    print("=== Samples & Showcase verification ===")
    print(f"Base: {BASE}")
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name} — {detail}")
    print(f"TOTAL: {passed} PASS / {failed} FAIL")

    report = REPO / "data" / "observability" / "samples_showcase_verify.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "base_url": BASE,
                "passed": passed,
                "failed": failed,
                "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Report: {report}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
