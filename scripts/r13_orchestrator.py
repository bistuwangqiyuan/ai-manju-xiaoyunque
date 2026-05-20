"""R13: 切换到聊斋·聂小倩古风 + Shell 2 refs 完整激活.

预期 vs R10/R11/R12:
- 内容切换:无限恐怖现代赛博 → 聊斋·聂小倩古风(公版IP无版权风险)
- 审核:古风内容 R8 历史验证宽松,Shell 2 refs 可激活
- Refs:5 张古风 ref(3 角色 + 2 场景)Jimeng T2I v30
- 目标:visual 提升 → 87-90/100
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
    os.environ.setdefault("VOLC_ACCESS_KEY", os.environ.get("VOLC_AK", ""))
    os.environ.setdefault("VOLC_SECRET_KEY", os.environ.get("VOLC_SK", ""))


# 古风 ref prompts (jimeng_t2i_v30 友好,无现代敏感词)
REF_PROMPTS = {
    "char_nie_xiaoqian": "Cinematic professional portrait of a beautiful young Asian woman in flowing white silk hanfu with pale pink ribbon sash, long black hair flowing past shoulders, a small vermillion red dot 朱砂痣 between her eyebrows, delicate pale features, mysterious gentle smile, ethereal cool moonlight blue lighting with subtle warm accent, Chinese ancient style aesthetic, professional photography, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "char_ning_caichen": "Cinematic professional portrait of a young Asian male scholar 24 years old in pale gray-blue traditional Chinese hanfu robe, black hair tied in a topknot with bamboo hairpin, holding a small paper lantern, gentle thoughtful expression, soft moonlight blue lighting with warm lantern glow on face, Chinese ancient style aesthetic, professional photography, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "char_yan_chixia": "Cinematic professional portrait of a serious Asian male swordsman 38 years old in dark navy Taoist robe with dark red cape, black hair tied in a high topknot, slight scar on right eyebrow, stern weathered features, carrying a brown leather pouch and short sword scabbard at waist, dramatic cool blue rim lighting with warm fill, Chinese ancient style aesthetic, professional photography, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "scene_lanruosi": "Cinematic wide shot of an abandoned ancient Chinese Buddhist temple at moonlit night, broken roof tiles, dilapidated wooden doors, overgrown bamboo groves, moonlight piercing through gaps, an empty altar, cool blue moonlight with subtle warm temple bell brass accents, eerie mystical atmosphere, photorealistic 35mm film grain, vertical 9:16 composition.",
    "scene_corridor": "Cinematic interior of an ancient Chinese temple east corridor at night, flickering candle on a wooden desk with paper scrolls and ink stone, dark wooden columns, moonlight from open window, warm candle glow against cool blue moonlight, mysterious atmosphere, photorealistic 35mm film grain, vertical 9:16 composition.",
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
        if captured: break
        time.sleep(0.5)
    if not captured:
        proc.terminate()
        raise RuntimeError("cloudflared URL not appearing")
    return proc, captured[0]


def verify_url(url: str, max_attempts: int = 60) -> bool:
    last_err = ""
    for i in range(max_attempts):
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
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
    print(f"    final: {last_err}")
    return False


def main() -> int:
    force_load_env(_REPO / ".env")
    print(f"=== R13 Orchestrator (聊斋·聂小倩 + Shell 2 refs) ===")

    refs_dir = _REPO / "data" / "refs" / "r13_nie_xiaoqian"
    refs_dir.mkdir(parents=True, exist_ok=True)

    # 生 5 张古风 ref
    for key, prompt in REF_PROMPTS.items():
        target = refs_dir / f"{key}.png"
        if target.exists() and target.stat().st_size > 10000:
            print(f"  [skip] {target.name}")
            continue
        print(f"  [gen] {target.name}...")
        try:
            png = call_jimeng_t2i(prompt)
            target.write_bytes(png)
            print(f"    ✓ saved {len(png)} bytes")
        except Exception as e:
            print(f"    ✗ FAIL: {e}")
    refs = {p.stem: p for p in refs_dir.glob("*.png")}
    print(f"  {len(refs)} refs ready: {sorted(refs.keys())}")

    # tunnel
    http_proc = start_http_server(refs_dir, 8767)
    time.sleep(2)
    try:
        tunnel_proc, public_url = start_cloudflared("http://localhost:8767")
        print(f"  Tunnel: {public_url}")
        sample = next(iter(refs))
        if not verify_url(f"{public_url}/{sample}.png"):
            return 1
        ref_url_map = {k: f"{public_url}/{k}.png" for k in refs}

        # Skylark 3 集 with refs
        from prompts.episodes import nie_xiaoqian_ch1 as nx
        from src.shell3_skylark_engine import (
            AigcMeta, EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
        )
        from src.shell5_post_production import master, MasterError
        from src.shell5_post_production.cinematic_master import MasterConfig

        # 角色 + 场景 ref 按集分配
        char_urls = [ref_url_map[k] for k in ("char_nie_xiaoqian", "char_ning_caichen", "char_yan_chixia") if k in ref_url_map]
        scene_map = {
            "ep01_lanruosi_moon": ["scene_lanruosi"],
            "ep02_three_knocks": ["scene_corridor"],
            "ep03_yan_chixia": ["scene_corridor"],  # 客栈室内,用回廊近似
        }
        print(f"  char_urls: {len(char_urls)} scene_per_ep: {list(scene_map.items())}")

        out_root = _REPO / "data" / "pilot_short_skylark"
        raw_dir = out_root / "raw_r13"
        raw_dir.mkdir(parents=True, exist_ok=True)
        run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
        manifest = {
            "run_id": f"R13_{run_id}",
            "round_id": "R13",
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "engine": "Skylark Agent 2.0 with Shell 2 古风 refs (聊斋·聂小倩切换)",
            "test_case": "聊斋·聂小倩 Chapter 1 三集 (公版IP,审核宽松)",
            "tunnel_public_url": public_url,
            "char_refs": char_urls,
            "episodes": [],
        }

        for ep in nx.EPISODES:
            ep_id = ep["ep_id"]
            print(f"\n  === {ep_id} ===")
            entry = {"id": ep_id, "ok": False}
            scene_refs = [ref_url_map[s] for s in scene_map.get(ep_id, []) if s in ref_url_map]
            ref_pack = ReferencePack(
                character_images=char_urls,
                scene_images=scene_refs,
            )
            meta = AigcMeta(
                content_producer="AI_MANJU_PILOT_R13_NIE_XIAOQIAN",
                producer_id=f"{ep_id}_R13_{run_id}_{uuid.uuid4().hex[:10]}",
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
            final_path = out_root / f"{ep_id}_r13.mp4"
            try:
                metrics = master(raw_path, final_path, ep_id=ep_id, task_id=result.task_id,
                                 config=MasterConfig(duration_cap_seconds=17.0))
            except MasterError as e:
                entry["error"] = f"master: {e}"
                manifest["episodes"].append(entry)
                continue
            entry.update({
                "ok": True, "task_id": result.task_id, "duration_preset_used": "～15s",
                "reported_output_seconds": result.output_duration_seconds,
                "aigc_meta_tagged": bool(result.aigc_meta_tagged),
                "raw_path": str(raw_path.resolve()), "final_path": str(final_path.resolve()),
                "master_metrics": metrics,
                "refs_used": {"character_images": char_urls, "scene_images": scene_refs},
            })
            manifest["episodes"].append(entry)
            print(f"    master OK: {metrics['width']}x{metrics['height']} @ {metrics['fps']} fps {metrics['bitrate_mbps']} Mbps")

        manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        manifest_path = out_root / "manifest_r13.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        ok = sum(1 for e in manifest["episodes"] if e.get("ok"))
        print(f"\n  R13 DONE: {ok}/3 successful. Manifest: {manifest_path}")
        return 0 if ok == 3 else 1
    finally:
        try: tunnel_proc.terminate()
        except Exception: pass
        try: http_proc.terminate()
        except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())
