"""Smoke-test the HappyHorse i2v fallback engine end-to-end.

Validates that:
  1. `happyhorse_client.is_configured()` is True locally (env var set).
  2. submit_i2v + query work against the real DashScope endpoint.
  3. The task reaches a non-PENDING status within ~6 minutes.

Set HAPPYHORSE_API_KEY before running. Costs ~¥0.5 per call.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "deploy", "cloudfn-slim"))

import happyhorse_client as hh  # noqa: E402

FIRST_FRAME = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/nie01_lanruosi.jpg"
PROMPT = (
    "聊斋·兰若惊鸿\n"
    "剧情：兰若寺夜雨初停，宁采臣独宿西厢。月光透窗，忽见一抹白影掠过回廊。\n"
    "视觉风格：古风3D国漫，9:16 竖屏短剧，镜头连贯、光影自然。"
)


def main() -> int:
    if not hh.is_configured():
        print("FAIL — HAPPYHORSE_API_KEY env var not set")
        return 1
    print(f"[1] submitting i2v: first_frame={FIRST_FRAME}")
    try:
        tid = hh.submit_i2v(FIRST_FRAME, PROMPT, resolution="720P", duration=5,
                            watermark=False)
    except hh.HappyHorseError as e:
        print(f"FAIL — submit_i2v: {e}")
        return 2
    print(f"    → task_id={tid}")

    deadline = time.time() + 360
    last_status = ""
    while time.time() < deadline:
        try:
            out = hh.query(tid)
        except hh.HappyHorseError as e:
            print(f"FAIL — query: {e}")
            return 3
        status = (out.get("task_status") or "").upper()
        if status != last_status:
            print(f"[2] status={status}")
            last_status = status
        if hh.is_terminal(status):
            if hh.is_success(status):
                video_url = out.get("video_url") or ""
                print(f"[OK] video_url={video_url[:96]}…")
                return 0
            print(f"FAIL — terminal={status} msg={out.get('message') or out.get('code')}")
            return 4
        time.sleep(15)
    print("FAIL — timeout (>6min)")
    return 5


if __name__ == "__main__":
    sys.exit(main())
