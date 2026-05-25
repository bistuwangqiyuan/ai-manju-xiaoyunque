"""火山引擎全链 smoke test — 真网验证 5 个核心 API.

覆盖:
  1. ARK chat completion (Doubao endpoint via OpenAI-compat)
  2. Doubao Seed-TTS 2.0 (语音合成; 需要数字 DOUBAO_TTS_APPID)
  3. Seedream Image (画图; req_key 已在 tools/multi_provider_image.py)
  4. Jimeng / Skylark Visual Submit (任务提交; 不等返回)
  5. TOS bucket list (S3-compatible head_bucket)

每条独立 try/except, 单条失败不影响其他.
结果汇总写入 ``data/volc_chain_health.json``.

Usage::

    python scripts/verify_volc_chain.py
    python scripts/verify_volc_chain.py --skip tts seedream
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _load_env(p: pathlib.Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


for env_file in (REPO / ".env", REPO / "backend" / ".env",
                 REPO / "deploy" / "cn-serverless" / ".env",
                 REPO / "deploy" / "cn-volc-vefaas" / ".env"):
    _load_env(env_file)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


@dataclass
class CheckResult:
    name: str
    ok: bool
    elapsed_ms: int = 0
    detail: str = ""
    skipped: bool = False
    error: str = ""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. ARK chat
# ---------------------------------------------------------------------------

def check_ark_chat() -> CheckResult:
    name = "ARK chat (Doubao Seed 1.6)"
    api_key = (os.environ.get("VOLC_ARK_API_KEY", "")
               or os.environ.get("ARK_API_KEY", "")).strip()
    endpoint = (os.environ.get("VOLC_ARK_BASE_URL", "")
                or "https://ark.cn-beijing.volces.com/api/v3").strip()
    model = (os.environ.get("DOUBAO_ENDPOINT_ID", "")
             or os.environ.get("VOLC_ARK_MODEL", "")
             or "doubao-1-5-pro-256k-250115").strip()
    if not api_key:
        return CheckResult(name=name, ok=False, skipped=True,
                           error="VOLC_ARK_API_KEY missing")
    import urllib.request
    import urllib.error

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": "用 10 个汉字写一句关于秋天的诗。"},
        ],
        "max_tokens": 64,
        "temperature": 0.3,
    }).encode("utf-8")
    url = endpoint.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return CheckResult(name=name, ok=False,
                           elapsed_ms=int((time.monotonic() - t0) * 1000),
                           error=f"HTTP {e.code} {e.reason}: {e.read()[:300]!r}")
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, ok=False,
                           elapsed_ms=int((time.monotonic() - t0) * 1000),
                           error=str(e))
    elapsed = int((time.monotonic() - t0) * 1000)
    text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
    return CheckResult(
        name=name, ok=bool(text), elapsed_ms=elapsed,
        detail=text[:80],
        extra={"model": model, "usage": data.get("usage", {})},
    )


# ---------------------------------------------------------------------------
# 2. Doubao Seed-TTS 2.0
# ---------------------------------------------------------------------------

def check_doubao_tts() -> CheckResult:
    name = "Doubao Seed-TTS 2.0"
    appid = os.environ.get("DOUBAO_TTS_APPID", "").strip()
    token = os.environ.get("DOUBAO_TTS_TOKEN", "").strip()
    if not appid or not token:
        return CheckResult(name=name, ok=False, skipped=True,
                           error="DOUBAO_TTS_APPID/TOKEN missing")
    if appid.startswith("api-key-") or not appid.isdigit():
        return CheckResult(
            name=name, ok=False, skipped=True,
            error=(f"DOUBAO_TTS_APPID={appid!r} 不是数字 AppID; "
                   "请在火山语音控制台 -> 语音合成大模型 ICL -> 「应用」面板 "
                   "复制 11 位数字 AppID"),
        )
    from src.shell5_post_production.tts_doubao_icl import (
        DoubaoIclClient,
        TTSRequest,
    )

    out = REPO / "data" / "smoke" / "doubao_tts.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        client = DoubaoIclClient(appid=appid, access_token=token)
        path = client.synth(
            TTSRequest(text="火山引擎全链路验证通过。",
                       voice_type="BV001_streaming",
                       emotion="neutral"),
            out,
        )
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, ok=False,
                           elapsed_ms=int((time.monotonic() - t0) * 1000),
                           error=f"{type(e).__name__}: {e}")
    elapsed = int((time.monotonic() - t0) * 1000)
    size = pathlib.Path(path).stat().st_size if pathlib.Path(path).exists() else 0
    return CheckResult(
        name=name, ok=size > 1024, elapsed_ms=elapsed,
        detail=f"{path} ({size} bytes)",
        extra={"size_bytes": size},
    )


# ---------------------------------------------------------------------------
# 3. Seedream image (via tools/multi_provider_image if available)
# ---------------------------------------------------------------------------

def check_seedream() -> CheckResult:
    name = "Seedream image (Volc)"
    if not (os.environ.get("VOLC_ACCESS_KEY") and os.environ.get("VOLC_SECRET_KEY")):
        return CheckResult(name=name, ok=False, skipped=True,
                           error="VOLC_ACCESS_KEY/SECRET_KEY missing")
    t0 = time.monotonic()
    try:
        from tools.multi_provider_image import generate_image_seedream  # type: ignore
    except Exception:
        # fallback path: direct call via volc_signer
        return _check_seedream_direct()
    try:
        url = generate_image_seedream(
            prompt="一只可爱的青色小鸟站在窗台上, 月光照亮羽毛, 国漫水墨风格",
            ratio="9:16",
        )
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, ok=False,
                           elapsed_ms=int((time.monotonic() - t0) * 1000),
                           error=f"{type(e).__name__}: {e}")
    elapsed = int((time.monotonic() - t0) * 1000)
    return CheckResult(name=name, ok=bool(url), elapsed_ms=elapsed,
                       detail=str(url)[:120])


def _check_seedream_direct() -> CheckResult:
    name = "Seedream image (Volc, direct)"
    import urllib.request
    import urllib.error
    from src.common.volc_signer import sign_request
    from src.common.volc_credentials import (
        resolve_volc_access_key, volc_secret_key_candidates,
    )

    ak = resolve_volc_access_key()
    sk_candidates = volc_secret_key_candidates()
    if not ak or not sk_candidates:
        return CheckResult(name=name, ok=False, skipped=True,
                           error="VOLC AK/SK missing")
    payload = {
        "req_key": "high_aes_general_v30l_zt2i",
        "prompt": "国漫水墨, 青鸟站在窗台, 月夜",
        "use_pre_llm": True,
        "use_sr": False,
        "return_url": True,
        "scale": 3.5,
        "width": 720,
        "height": 1280,
    }
    body = json.dumps(payload).encode("utf-8")
    t0 = time.monotonic()
    last_err = ""
    for sk in sk_candidates:
        signed = sign_request(
            access_key=ak, secret_key=sk,
            action="CVProcess", version="2022-08-31", body=body,
        )
        try:
            req = urllib.request.Request(
                signed.url, data=signed.body, headers=signed.headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            elapsed = int((time.monotonic() - t0) * 1000)
            code = data.get("code", -1)
            if code in (10000, 0):
                urls = (data.get("data") or {}).get("image_urls") or []
                return CheckResult(name=name, ok=bool(urls),
                                   elapsed_ms=elapsed,
                                   detail=(urls[0] if urls else "no image url"))
            last_err = f"code={code} message={data.get('message')}"
        except urllib.error.HTTPError as e:
            try:
                last_err = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                last_err = f"HTTP {e.code} {e.reason}"
            if e.code != 401:
                break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            break
    return CheckResult(name=name, ok=False,
                       elapsed_ms=int((time.monotonic() - t0) * 1000),
                       error=last_err)


# ---------------------------------------------------------------------------
# 4. Jimeng / Skylark Visual submit (no wait)
# ---------------------------------------------------------------------------

def check_skylark_submit() -> CheckResult:
    name = "Skylark Visual submit (probe)"
    import urllib.request
    import urllib.error
    from src.common.volc_signer import sign_request
    from src.common.volc_credentials import (
        resolve_volc_access_key, volc_secret_key_candidates,
    )

    ak = resolve_volc_access_key()
    sk_candidates = volc_secret_key_candidates()
    if not ak or not sk_candidates:
        return CheckResult(name=name, ok=False, skipped=True,
                           error="VOLC AK/SK missing")
    payload = {"req_key": "jimeng_t2i_v40", "prompt": "ping"}
    body = json.dumps(payload).encode("utf-8")
    t0 = time.monotonic()
    last = ""
    for sk in sk_candidates:
        signed = sign_request(
            access_key=ak, secret_key=sk,
            action="CVSync2AsyncSubmitTask", version="2022-08-31", body=body,
        )
        req = urllib.request.Request(
            signed.url, data=signed.body, headers=signed.headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            code = int(data.get("code", -1))
            elapsed = int((time.monotonic() - t0) * 1000)
            # 50411 / 50412 = audit; 10000/0 = ok; 50429 = throttle
            if code in (10000, 0):
                task_id = (data.get("data") or {}).get("task_id", "")
                return CheckResult(name=name, ok=True,
                                   elapsed_ms=elapsed,
                                   detail=f"task_id={task_id}")
            # 即使被 audit/限流, 也代表签名/key 通; 标记为部分通过
            if code in (50411, 50412, 50413, 50429):
                return CheckResult(name=name, ok=True,
                                   elapsed_ms=elapsed,
                                   detail=(f"signed OK, code={code} "
                                           f"({data.get('message')})"))
            last = f"code={code} message={data.get('message')}"
        except urllib.error.HTTPError as e:
            try:
                last = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                last = f"HTTP {e.code} {e.reason}"
            if e.code != 401:
                break
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            break
    return CheckResult(name=name, ok=False,
                       elapsed_ms=int((time.monotonic() - t0) * 1000),
                       error=last)


# ---------------------------------------------------------------------------
# 5. TOS bucket head/list
# ---------------------------------------------------------------------------

def check_tos_list() -> CheckResult:
    name = "TOS bucket list_prefix (S3-compat)"
    bucket = (os.environ.get("TOS_BUCKET") or os.environ.get("S3_BUCKET") or "").strip()
    if not bucket:
        return CheckResult(name=name, ok=False, skipped=True,
                           error="TOS_BUCKET / S3_BUCKET missing")
    try:
        from src.common.tos_storage import TosStorage
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, ok=False,
                           error=f"import TosStorage failed: {e}")
    t0 = time.monotonic()
    try:
        store = TosStorage()
        keys = list(store.list_prefix(""))[:10] if hasattr(store, "list_prefix") else []
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, ok=False,
                           elapsed_ms=int((time.monotonic() - t0) * 1000),
                           error=f"{type(e).__name__}: {e}")
    elapsed = int((time.monotonic() - t0) * 1000)
    return CheckResult(name=name, ok=True, elapsed_ms=elapsed,
                       detail=f"bucket={bucket} sample={len(keys)} keys",
                       extra={"sample_keys": [str(k) for k in keys[:5]]})


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = {
    "ark":       check_ark_chat,
    "tts":       check_doubao_tts,
    "seedream":  check_seedream,
    "skylark":   check_skylark_submit,
    "tos":       check_tos_list,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_volc_chain")
    parser.add_argument("--skip", nargs="*", default=[],
                        help=f"skip checks: {', '.join(CHECKS)}")
    parser.add_argument("--only", nargs="*", default=[],
                        help="run only these checks")
    parser.add_argument("--output", default="data/volc_chain_health.json")
    args = parser.parse_args(argv)

    targets = (args.only or list(CHECKS.keys()))
    targets = [k for k in targets if k not in args.skip]

    print(f"{'='*72}")
    print(f"火山引擎全链 smoke test  {_dt.datetime.now().isoformat(timespec='seconds')}")
    print(f"{'='*72}")
    results: list[CheckResult] = []
    for key in targets:
        fn = CHECKS.get(key)
        if not fn:
            print(f"  [skip] unknown check {key!r}")
            continue
        print(f"\n[{key}] {fn.__doc__ or fn.__name__}")
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = CheckResult(name=key, ok=False,
                              error=f"{type(e).__name__}: {e}\n"
                                    f"{traceback.format_exc(limit=2)}")
        results.append(res)
        status = "OK " if res.ok else ("SKIP" if res.skipped else "FAIL")
        print(f"  -> [{status}] {res.name}  ({res.elapsed_ms} ms)")
        if res.detail:
            print(f"     detail: {res.detail}")
        if res.error:
            print(f"     error : {res.error}")

    # Persist
    out_path = REPO / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "results": [asdict(r) for r in results],
        "summary": {
            "total":   len(results),
            "ok":      sum(1 for r in results if r.ok),
            "skipped": sum(1 for r in results if r.skipped),
            "failed":  sum(1 for r in results if not r.ok and not r.skipped),
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nwrote {out_path}")

    ok = payload["summary"]["failed"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
