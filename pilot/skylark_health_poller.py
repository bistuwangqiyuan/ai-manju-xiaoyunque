"""后台轮询 Volcengine Skylark API 健康状态.

每 90s 发一个最小代价的 GetResult 探针（带已知 task_id），观察 50400 是否清除。
- 50400 → 写 `data/skylark_health.log` 状态行
- 任何 2xx 或 50404（task not found，签名 OK 只是 task 不存在）→ API 恢复，写 STATE=OK 退出

退出码 0：API 恢复
退出码 124：超过最大轮询时长（默认 30 min）未恢复
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from pilot.run_three_short_episodes import load_env_file  # noqa: E402
from src.common.volc_credentials import (  # noqa: E402
    resolve_volc_access_key,
    volc_secret_key_candidates,
)
from src.common.volc_signer import sign_request  # noqa: E402


POLL_INTERVAL_SECONDS = 90
MAX_DURATION_SECONDS = 30 * 60   # 30 min
PROBE_TASK_ID = "6345109403728609756"  # 今早 03:19 成功调用的真 task_id（12h 内有效）
HEALTH_LOG = _REPO / "data" / "skylark_health.log"


def probe_once(ak: str, sk: str) -> tuple[int, str]:
    """发一次 GetResult 探针，返回 (skylark_code, message)。"""

    body = json.dumps({
        "req_key": "pippit_iv2v_v20_cvtob_with_vinput",
        "task_id": PROBE_TASK_ID,
    }, ensure_ascii=False).encode("utf-8")
    signed = sign_request(
        access_key=ak, secret_key=sk,
        action="CVSync2AsyncGetResult", version="2022-08-31",
        body=body,
    )
    req = urllib.request.Request(
        signed.url, data=signed.body, headers=signed.headers, method=signed.method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            return int(d.get("code", -1)), (d.get("message") or "")[:200]
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            d = json.loads(body)
            return int(d.get("code", e.code)), (d.get("message") or "")[:200]
        except Exception:
            return e.code, body[:200].decode("utf-8", errors="replace")
    except Exception as exc:
        return -1, f"{type(exc).__name__}: {exc}"


def main() -> int:
    load_env_file(_REPO / ".env")
    ak = resolve_volc_access_key()
    candidates = volc_secret_key_candidates()
    if not ak or not candidates:
        print("[fatal] missing VOLC_AK / VOLC_SK in .env")
        return 1

    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    started = _dt.datetime.now(_dt.timezone.utc)
    end_deadline = started + _dt.timedelta(seconds=MAX_DURATION_SECONDS)

    print(f"[start] Skylark health poll started at {started.isoformat()}; "
          f"deadline {end_deadline.isoformat()}; interval={POLL_INTERVAL_SECONDS}s")

    poll_idx = 0
    while _dt.datetime.now(_dt.timezone.utc) < end_deadline:
        poll_idx += 1
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
        code, msg = probe_once(ak, candidates[0])
        # Skylark 成功语义：
        #   10000 = OK (会有 task data)
        #   50404 = task_id not_found (签名 OK，只是 task 没找到)
        #   其他状态码 = 各种错误
        # 50400 / 50401 / 50403 = 鉴权失败（账户阻塞）
        # 50429 / 50430 / 50500 = 临时性可重试
        is_auth_ok = code in (10000, 50404) or (code >= 10000 and code != 50400 and code != 50401 and code != 50403)
        status = "OK" if is_auth_ok else "BLOCKED"
        line = f"{ts}\tpoll#{poll_idx}\t{status}\tcode={code}\tmsg={msg}\n"
        HEALTH_LOG.write_text(
            HEALTH_LOG.read_text(encoding="utf-8") + line if HEALTH_LOG.exists() else line,
            encoding="utf-8",
        )
        print(line.strip())

        if is_auth_ok:
            print(f"[RECOVERY] Skylark API access restored after {poll_idx} probes "
                  f"({(_dt.datetime.now(_dt.timezone.utc) - started).total_seconds():.0f}s). "
                  f"Re-run `python pilot/run_three_short_episodes.py` for fresh 60s episodes.")
            return 0

        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"[timeout] {MAX_DURATION_SECONDS}s elapsed, Skylark API still blocked. "
          f"Total probes: {poll_idx}. Last code: {code}, last msg: {msg!r}")
    return 124


if __name__ == "__main__":
    raise SystemExit(main())
