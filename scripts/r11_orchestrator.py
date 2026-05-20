"""R11 完整 orchestrator: Shell 2 角色/场景 refs + cloudflared tunnel + Skylark.

流程:
1. force-override load .env (含 VOLC_AK/SK)
2. 用 Jimeng T2I v3.0 (req_key=jimeng_t2i_v30) 生成 4 角色 + 3 场景共 7 张 ref，base64 落盘
3. 启动 http.server (port 8765) 暴露 data/refs/r11/
4. 启动 cloudflared quick tunnel，捕获 https://*.trycloudflare.com 公网 URL
5. 验证公网 URL 可达
6. 用 R11 v2 plot 提交 Skylark 3 集，img_url_list=[char + scene URLs]
7. 母带精修
8. 写 manifest
"""
from __future__ import annotations

import base64
import datetime as _dt
import io
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
    # 镜像 VOLC_AK → VOLC_ACCESS_KEY 等别名
    if not os.environ.get("VOLC_ACCESS_KEY"):
        os.environ["VOLC_ACCESS_KEY"] = os.environ.get("VOLC_AK", "")
    if not os.environ.get("VOLC_SECRET_KEY"):
        os.environ["VOLC_SECRET_KEY"] = os.environ.get("VOLC_SK", "")


# Jimeng T2I v3.0 (Volcengine Visual, sync) prompts for 4 chars + 3 scenes.
# Style anchor: cinematic teal-orange, high-quality professional photography.
REF_PROMPTS = {
    "char_zhengzha": "Cinematic professional portrait of a young Asian office worker, 24 years old, slim build, messy short black hair, light blue collared shirt with rolled-up sleeves, dark gray slacks, dilated bewildered eyes, photographic realism, dramatic teal-blue shadow and warm orange highlight cinematic lighting, 35mm film grain, vertical 9:16 portrait orientation. Plain neutral gray background.",
    "char_zhangjie": "Cinematic professional portrait of a 24-year-old Asian young man with shoulder-length tousled black hair partly covering forehead, multiple intersecting scar lines crossing his face from forehead to jaw in dark red, dark high-neck shirt under olive-green tactical jacket, holding a cigarette between two fingers, smoke drifting, intense cold gaze, photographic realism, dramatic teal-blue and warm orange cinematic lighting, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "char_glasses_woman": "Cinematic professional portrait of a 25-year-old Asian professional woman, long straight black hair tied back, round metal-frame eyeglasses, light gray collared blouse with sleeves neatly buttoned, dark gray trousers, calm intelligent expression, photographic realism, soft cool teal-blue rim lighting with warm fill light, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "char_matthew": "Cinematic professional portrait of a 38-year-old African-American man, short military-cut black hair, black tactical vest over olive-green T-shirt, tactical belt, stern leadership expression, gold-tinted dramatic rim lighting, photographic realism, 35mm film grain, vertical 9:16 portrait. Plain neutral gray background.",
    "scene_office": "Cinematic wide shot of an empty modern open-plan office at midnight, dim work cubicles in background shadow, single desktop monitor glowing cold blue-white on a desk, scattered coffee cups and notebooks, city lights blurred through window in distance, photorealistic 35mm film grain, dark teal-blue palette with warm desk-lamp orange accents, vertical 9:16 composition.",
    "scene_cabin": "Cinematic interior of a fast-moving futuristic train cabin, criss-crossing metal pipes, intermittent red emergency lighting on ceiling, thin layer of condensation reflecting on metal floor, cyberpunk industrial design, photorealistic 35mm film grain, dark teal-blue palette with warm red emergency accents, vertical 9:16 composition.",
    "scene_platform": "Cinematic wide shot of a dark industrial underground subway platform with metal grating floor, hexagonal massive sliding door in the distance with cold blue LED status lights, fog and atmospheric depth, photorealistic 35mm film grain, dark teal-blue palette with warm orange LED accents, vertical 9:16 composition.",
}


def call_jimeng_t2i(prompt: str, width: int = 768, height: int = 1024) -> bytes:
    """同步调 Volcengine Visual jimeng_t2i_v30 返回 PNG bytes."""

    from src.common.volc_signer import sign_request

    payload = {
        "req_key": "jimeng_t2i_v30",
        "prompt": prompt,
        "width": width,
        "height": height,
    }
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
        raise RuntimeError(f"Jimeng T2I error: {data.get('message')}")
    d = data.get("data", {})
    b64 = d.get("binary_data_base64") or d.get("binary_data")
    if isinstance(b64, list):
        b64 = b64[0]
    if not b64:
        raise RuntimeError(f"Jimeng T2I no binary_data_base64 in response keys={list(d.keys())}")
    return base64.b64decode(b64)


def gen_all_refs(out_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    """生成 7 张 ref，落盘返回 {key: path}。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, pathlib.Path] = {}
    for key, prompt in REF_PROMPTS.items():
        out_path = out_dir / f"{key}.png"
        if out_path.exists() and out_path.stat().st_size > 10000:
            print(f"  [skip-existing] {key}: {out_path.stat().st_size} bytes")
            result[key] = out_path
            continue
        print(f"  [gen] {key}...")
        try:
            png = call_jimeng_t2i(prompt)
            out_path.write_bytes(png)
            print(f"    ✓ saved {len(png)} bytes")
            result[key] = out_path
        except Exception as e:
            print(f"    ✗ FAIL: {type(e).__name__}: {str(e)[:160]}")
    return result


def start_http_server(directory: pathlib.Path, port: int) -> subprocess.Popen:
    """在后台用 python http.server serve directory。"""

    cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
           "--directory", str(directory)]
    print(f"  http.server: {' '.join(cmd)}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_cloudflared_tunnel(local_url: str) -> tuple[subprocess.Popen, str]:
    """启动 cloudflared quick tunnel, 解析 stdout 抓取公网 URL。"""

    cmd = ["cloudflared", "tunnel", "--url", local_url, "--no-autoupdate"]
    print(f"  cloudflared: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)

    url_re = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
    captured_url: list[str] = []

    def reader():
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            m = url_re.search(line)
            if m and not captured_url:
                captured_url.append(m.group(0))
            if not captured_url and ("error" in line.lower() or "warn" in line.lower()):
                print(f"    cloudflared: {line[:160]}")

    threading.Thread(target=reader, daemon=True).start()

    # 等 URL 出现，最长 30s
    for _ in range(60):
        if captured_url:
            break
        time.sleep(0.5)
    if not captured_url:
        proc.terminate()
        raise RuntimeError("cloudflared tunnel URL did not appear within 30s")
    return proc, captured_url[0]


def verify_url(url: str, max_attempts: int = 20) -> bool:
    """轮询 URL 直到 HTTP 200(cloudflared 隧道 DNS 传播延迟)。"""
    for i in range(max_attempts):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main() -> int:
    force_load_env(_REPO / ".env")
    print(f"=== R11 Orchestrator ===")
    print(f"  VOLC_AK present: {bool(os.environ.get('VOLC_ACCESS_KEY'))}")

    # Step 1: 生 refs
    refs_dir = _REPO / "data" / "refs" / "r11"
    print(f"\n--- Step 1: Generate Jimeng T2I refs → {refs_dir} ---")
    ref_paths = gen_all_refs(refs_dir)
    if not ref_paths:
        print("ERROR: no refs generated")
        return 1
    print(f"  Generated {len(ref_paths)} refs.")

    # Step 2: http.server
    print(f"\n--- Step 2: Start http.server on :8765 ---")
    http_proc = start_http_server(refs_dir, 8765)
    time.sleep(2)
    if http_proc.poll() is not None:
        print(f"ERROR: http.server died (exit={http_proc.returncode})")
        return 1

    # Step 3: cloudflared tunnel
    try:
        print(f"\n--- Step 3: Start cloudflared quick tunnel ---")
        tunnel_proc, public_url = start_cloudflared_tunnel("http://localhost:8765")
        print(f"  Public URL: {public_url}")

        # Step 4: verify
        print(f"\n--- Step 4: Verify public URL reachability ---")
        sample_ref = next(iter(ref_paths))
        test_url = f"{public_url}/{sample_ref}.png"
        print(f"  Probing {test_url}...")
        if not verify_url(test_url):
            print(f"ERROR: public URL not reachable after retries")
            tunnel_proc.terminate()
            http_proc.terminate()
            return 1
        print(f"  ✓ Public URL reachable")

        # Step 5: build URL map
        ref_url_map = {k: f"{public_url}/{k}.png" for k in ref_paths}
        (refs_dir / "_url_map.json").write_text(
            json.dumps({"public_base": public_url, "refs": ref_url_map},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Step 6: Skylark generate 3 episodes with refs
        print(f"\n--- Step 5: Skylark generate 3 eps with img_url_list ---")
        from prompts.episodes import infinite_horror_ch1_v2 as v2
        from src.shell3_skylark_engine import (
            AigcMeta, EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
        )
        from src.shell5_post_production import master, MasterError
        from src.shell5_post_production.cinematic_master import MasterConfig

        # 角色 ref 4 张共用 + 场景 ref 按集分配
        char_urls = [ref_url_map[k] for k in ("char_zhengzha", "char_zhangjie", "char_glasses_woman", "char_matthew") if k in ref_url_map]
        scene_url = {
            "ep01_office_yes": [ref_url_map["scene_office"]] if "scene_office" in ref_url_map else [],
            "ep02_cabin_threat": [ref_url_map["scene_cabin"]] if "scene_cabin" in ref_url_map else [],
            "ep03_arrive_door": [ref_url_map["scene_platform"]] if "scene_platform" in ref_url_map else [],
        }

        out_root = _REPO / "data" / "pilot_short_skylark"
        raw_dir = out_root / "raw_r11"
        raw_dir.mkdir(parents=True, exist_ok=True)
        run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")

        manifest = {
            "run_id": f"R11_{run_id}",
            "round_id": "R11",
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "engine": "Skylark Agent 2.0 = Seedance 2.0 fast 720p with reference (refs INJECTED)",
            "shell2_refs_public_base": public_url,
            "shell2_char_refs": [ref_url_map.get(k) for k in ("char_zhengzha","char_zhangjie","char_glasses_woman","char_matthew")],
            "episodes": [],
        }

        for ep in v2.EPISODES:
            ep_id = ep["ep_id"]
            print(f"\n  === {ep_id} ===")
            entry = {"id": ep_id, "ok": False}
            ref_pack = ReferencePack(
                character_images=char_urls,
                scene_images=scene_url.get(ep_id, []),
            )
            meta = AigcMeta(
                content_producer="AI_MANJU_PILOT_R11_INFINITE_HORROR",
                producer_id=f"{ep_id}_R11_{run_id}_{uuid.uuid4().hex[:10]}",
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
            final_path = out_root / f"{ep_id}.mp4"
            try:
                metrics = master(raw_path, final_path, ep_id=ep_id, task_id=result.task_id,
                                 config=MasterConfig(duration_cap_seconds=17.0))
            except MasterError as e:
                print(f"    master FAIL: {str(e)[:200]}")
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
                "refs_used": {
                    "character_images": char_urls,
                    "scene_images": scene_url.get(ep_id, []),
                },
            })
            manifest["episodes"].append(entry)
            print(f"    master OK: {metrics['width']}x{metrics['height']} @ {metrics['fps']} fps")

        manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        (out_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  Manifest written. Successes: {sum(1 for e in manifest['episodes'] if e.get('ok'))}/{len(manifest['episodes'])}")
    finally:
        print("\n  Stopping tunnel + http.server...")
        try:
            tunnel_proc.terminate()
        except Exception:
            pass
        try:
            http_proc.terminate()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
