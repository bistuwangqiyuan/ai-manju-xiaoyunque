"""R12: audit-safe pipeline — refs softened, prompts softened, Shell 2 active.

R11 教训:
- char_zhangjie/char_matthew refs 触发 50411 Pre Img Risk
- 英文 prompt 含武器/暴力词触发 50412 Text Risk

R12 修复:
- 重新生成 2 张 audit-safe refs (生活化形象,无工装/疤痕)
- 用 infinite_horror_ch1_v3.py (软化 prompts,无英文武器/暴力)
- 复用 R11 已生成的 5 张其他 refs
- 重启 cloudflared tunnel
- Skylark 3 集 with img_url_list
- master + score
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def force_load_env(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip()
        if k and v:
            os.environ[k.strip()] = v
    if not os.environ.get("VOLC_ACCESS_KEY"):
        os.environ["VOLC_ACCESS_KEY"] = os.environ.get("VOLC_AK", "")
    if not os.environ.get("VOLC_SECRET_KEY"):
        os.environ["VOLC_SECRET_KEY"] = os.environ.get("VOLC_SK", "")


# Audit-safe ref prompts (生活化形象)
SAFE_REF_PROMPTS = {
    "char_zhangjie_v2": "Cinematic professional portrait of a 24-year-old Asian young man with shoulder-length tousled black hair, weathered features, dark high-neck sweater under dark coat, contemplative serious expression, soft cool teal-blue rim lighting with warm fill light, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "char_matthew_v2": "Cinematic professional portrait of a 38-year-old African-American man, short military-cut black hair, dark navy uniform shirt, calm authoritative expression, gold-tinted dramatic rim lighting, photographic realism, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
}


def call_jimeng_t2i(prompt: str, width: int = 768, height: int = 1024) -> bytes:
    from src.common.volc_signer import sign_request
    payload = {"req_key": "jimeng_t2i_v30", "prompt": prompt, "width": width, "height": height}
    body = json.dumps(payload).encode("utf-8")
    signed = sign_request(
        access_key=os.environ["VOLC_ACCESS_KEY"],
        secret_key=os.environ["VOLC_SECRET_KEY"],
        action="CVProcess", version="2022-08-31", body=body,
    )
    req = urllib.request.Request(signed.url, data=signed.body, headers=signed.headers, method=signed.method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 10000:
        raise RuntimeError(f"Jimeng error: {data.get('message')}")
    d = data.get("data", {})
    b64 = d.get("binary_data_base64") or d.get("binary_data")
    if isinstance(b64, list):
        b64 = b64[0]
    return base64.b64decode(b64)


def start_http_server(directory: pathlib.Path, port: int) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
           "--directory", str(directory)]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_cloudflared(local_url: str) -> tuple[subprocess.Popen, str]:
    cmd = ["cloudflared", "tunnel", "--url", local_url, "--no-autoupdate"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    # 真 quick tunnel URL 形如 https://word-word-word-word.trycloudflare.com (3+ hyphens)
    # 排除 api.trycloudflare.com (cloudflare 自己的 API endpoint,不是隧道)
    url_re = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+){2,}\.trycloudflare\.com")
    captured: list[str] = []

    def reader():
        for line in iter(proc.stdout.readline, ""):
            if line and not captured:
                m = url_re.search(line)
                if m and "api.trycloudflare.com" not in m.group(0):
                    captured.append(m.group(0))
                    print(f"  cloudflared output: {line.rstrip()[:160]}")

    threading.Thread(target=reader, daemon=True).start()
    for _ in range(60):
        if captured:
            break
        time.sleep(0.5)
    if not captured:
        proc.terminate()
        raise RuntimeError("cloudflared URL not appearing in 30s")
    return proc, captured[0]


def verify_url(url: str, max_attempts: int = 60) -> bool:
    """轮询 URL 等 cloudflared DNS 传播(可能要 60-120s)。用 GET 代替 HEAD(部分代理不支持 HEAD)。"""
    last_err = ""
    for i in range(max_attempts):
        try:
            req = urllib.request.Request(url, method="GET",
                                          headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    print(f"    URL reachable after {i*2}s")
                    return True
                last_err = f"HTTP {resp.status}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"
        if i % 10 == 0 and i > 0:
            print(f"    waiting... {i*2}s elapsed (last: {last_err})")
        time.sleep(2)
    print(f"    final attempt failed: {last_err}")
    return False


def main() -> int:
    force_load_env(_REPO / ".env")
    print(f"=== R12 Orchestrator (audit-safe refs + prompts) ===")

    refs_dir = _REPO / "data" / "refs" / "r12"
    refs_dir.mkdir(parents=True, exist_ok=True)

    # 1. 复用 R11 的 5 张安全 refs (郑吒+眼镜女+3 场景)
    r11_dir = _REPO / "data" / "refs" / "r11"
    for k in ("char_zhengzha", "char_glasses_woman", "scene_office", "scene_cabin", "scene_platform"):
        src = r11_dir / f"{k}.png"
        if src.exists():
            shutil.copy2(src, refs_dir / f"{k}.png")
            print(f"  reuse R11 ref: {k}")

    # 2. 重新生成 2 张 audit-safe refs
    for key, prompt in SAFE_REF_PROMPTS.items():
        # rename _v2 to match R11 naming, then save under proper name (drop _v2 suffix for img_url consistency)
        target = refs_dir / f"{key.replace('_v2', '')}.png"
        if target.exists() and target.stat().st_size > 10000:
            print(f"  [skip] {target.name}")
            continue
        print(f"  [regen-safe] {target.name}...")
        try:
            png = call_jimeng_t2i(prompt)
            target.write_bytes(png)
            print(f"    ✓ saved {len(png)} bytes")
        except Exception as e:
            print(f"    ✗ FAIL: {e}")

    refs = {p.stem: p for p in refs_dir.glob("*.png")}
    print(f"  {len(refs)} refs ready: {sorted(refs.keys())}")

    # 3. http.server + cloudflared
    http_proc = start_http_server(refs_dir, 8766)
    time.sleep(2)

    try:
        tunnel_proc, public_url = start_cloudflared("http://localhost:8766")
        print(f"  Tunnel: {public_url}")
        sample = next(iter(refs))
        test_url = f"{public_url}/{sample}.png"
        if not verify_url(test_url):
            print(f"  ERROR: public URL not reachable")
            return 1
        print(f"  ✓ Public URL reachable")

        ref_url_map = {k: f"{public_url}/{k}.png" for k in refs}

        # 4. Skylark generate 3 eps with v3 prompts
        from prompts.episodes import infinite_horror_ch1_v3 as v3
        from src.shell3_skylark_engine import (
            AigcMeta, EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
        )
        from src.shell5_post_production import master, MasterError
        from src.shell5_post_production.cinematic_master import MasterConfig

        char_urls = [ref_url_map[k] for k in ("char_zhengzha", "char_zhangjie", "char_glasses_woman", "char_matthew") if k in ref_url_map]
        scene_url = {
            "ep01_office_yes": [ref_url_map.get("scene_office")] if "scene_office" in ref_url_map else [],
            "ep02_cabin_threat": [ref_url_map.get("scene_cabin")] if "scene_cabin" in ref_url_map else [],
            "ep03_arrive_door": [ref_url_map.get("scene_platform")] if "scene_platform" in ref_url_map else [],
        }
        print(f"  char_urls: {len(char_urls)}, scene per-ep: {[(k, len(v)) for k,v in scene_url.items()]}")

        out_root = _REPO / "data" / "pilot_short_skylark"
        raw_dir = out_root / "raw_r12"
        raw_dir.mkdir(parents=True, exist_ok=True)
        run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
        manifest = {
            "run_id": f"R12_{run_id}",
            "round_id": "R12",
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "engine": "Skylark Agent 2.0 with Shell 2 audit-safe refs",
            "tunnel_public_url": public_url,
            "char_refs": char_urls,
            "scene_refs_per_ep": scene_url,
            "episodes": [],
        }

        for ep in v3.EPISODES:
            ep_id = ep["ep_id"]
            print(f"\n  === {ep_id} ===")
            entry = {"id": ep_id, "ok": False}
            ref_pack = ReferencePack(
                character_images=char_urls,
                scene_images=scene_url.get(ep_id, []),
            )
            meta = AigcMeta(
                content_producer="AI_MANJU_PILOT_R12",
                producer_id=f"{ep_id}_R12_{run_id}_{uuid.uuid4().hex[:10]}",
                content_propagator="AI_MANJU_INTERNAL_TEST",
                propagate_id=f"prop_{ep_id}",
            )
            client = SkylarkAgentV2WithRefClient(poll_interval_seconds=12.0, timeout_seconds=7200.0, aigc_meta=meta)
            req = EpisodeRequest(
                prompt=ep["prompt"][:2000],
                references=ref_pack,
                ratio="9:16", duration="～15s", language="Chinese",
                enable_watermark=False,
            )
            try:
                result = client.render_episode(req, ep_id=ep_id)
            except Exception as e:
                print(f"    Skylark FAIL: {str(e)[:200]}")
                entry["error"] = f"skylark: {e}"
                manifest["episodes"].append(entry)
                continue
            print(f"    Skylark OK: task_id={result.task_id} dur={result.output_duration_seconds:.2f}s")
            raw_path = raw_dir / f"{ep_id}.raw.mp4"
            shutil.copy2(result.archived_video_path, raw_path)
            # R12 outputs go to ep0X_r12.mp4 to avoid overwriting parallel agent's mp4s
            final_path = out_root / f"{ep_id}_r12.mp4"
            try:
                metrics = master(raw_path, final_path, ep_id=ep_id, task_id=result.task_id,
                                 config=MasterConfig(duration_cap_seconds=17.0))
            except MasterError as e:
                entry["error"] = f"master: {e}"
                manifest["episodes"].append(entry)
                continue
            entry.update({
                "ok": True,
                "task_id": result.task_id,
                "duration_preset_used": "～15s",
                "reported_output_seconds": result.output_duration_seconds,
                "aigc_meta_tagged": bool(result.aigc_meta_tagged),
                "raw_path": str(raw_path.resolve()),
                "final_path": str(final_path.resolve()),
                "master_metrics": metrics,
                "refs_used": {"character_images": char_urls, "scene_images": scene_url.get(ep_id, [])},
            })
            manifest["episodes"].append(entry)

        manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        manifest_path = out_root / "manifest_r12.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = sum(1 for e in manifest["episodes"] if e.get("ok"))
        print(f"\n  R12 DONE: {ok}/3 successful. Manifest: {manifest_path}")
    finally:
        try: tunnel_proc.terminate()
        except Exception: pass
        try: http_proc.terminate()
        except Exception: pass
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
