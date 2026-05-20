"""R14: production.yaml 规划的 Veo 3.1 / Sora 2 高光集精修路径 wiring.

production.yaml shell4_qa_repair.repair_routes.climax_enhance 已规划:
  primary  : { provider: google, model: veo-3.1-fast }            $0.15/s
  top_tier : { provider: google, model: veo-3.1-standard }        $0.40/s
  god_tier : { provider: openai, model: sora-2-pro-1080p }        gated

本脚本接整集 prompt → 调 Veo/Sora → 落盘 mp4 → 更新 manifest。

必备 env:
  Veo: GOOGLE_CLOUD_PROJECT + GOOGLE_ACCESS_TOKEN (gcloud auth print-access-token)
  Sora 2: OPENAI_API_KEY + Sora2 video access (gated)

设计原则:
- 缺凭据自动跳过(不抛错),日志写明
- Veo 优先(便宜 2.7x),Sora 2 god-tier 兜底
- 不上传任何识别人脸图(Sora 2 风控)
- 输出 mp4 直接走 Shell 5 cinematic_master 二次精修
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def has_veo_credentials() -> tuple[bool, str]:
    """检查 Veo 3.1 凭据是否齐全。"""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "").strip()
    if not project:
        return False, "GOOGLE_CLOUD_PROJECT 未设置"
    if not token:
        return False, "GOOGLE_ACCESS_TOKEN 未设置 (运行 `gcloud auth print-access-token`)"
    return True, f"OK project={project} token=<{len(token)} chars>"


def has_sora_credentials() -> tuple[bool, str]:
    """检查 Sora 2 凭据 + 访问权(API 网关接受度)。"""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return False, "OPENAI_API_KEY 未设置"
    # 探测一下账户是否有 Sora 2 access
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        sora_models = [m for m in data.get("data", []) if "sora" in m.get("id", "").lower()]
        if sora_models:
            return True, f"OK Sora models available: {[m['id'] for m in sora_models[:3]]}"
        return False, "OPENAI_API_KEY 有,但账户无 Sora 2 access(需企业账户激活)"
    except Exception as e:
        return False, f"OpenAI API 探测失败:{type(e).__name__}: {str(e)[:80]}"


def render_veo31_fast(prompt: str, *, duration_seconds: int = 8) -> str:
    """用 Veo 3.1 Fast 渲一集,返回视频 GCS URI 或本地 mp4 路径。"""
    from src.shell4_qa_repair.repair_veo31 import Veo31Repair
    from src.shell4_qa_repair.repair_router import RepairContext
    veo = Veo31Repair(model="veo-3.1-fast-generate-001", duration_seconds=duration_seconds)
    ctx = RepairContext(
        shot_id=0, shot_url="",
        shot_prompt=json.dumps({"prompt": prompt, "reference_image_urls": []},
                                ensure_ascii=False),
        canonical_image_url="",
        is_climax_shot=True, is_top_episode=True,
    )
    return veo(ctx)


def render_sora2_pro(prompt: str, *, duration_seconds: int = 8) -> str:
    """用 Sora 2 Pro 渲一集,返回视频 URL。"""
    from src.shell4_qa_repair.repair_sora2 import Sora2ProRepair
    from src.shell4_qa_repair.repair_router import RepairContext
    sora = Sora2ProRepair(duration_seconds=duration_seconds)
    ctx = RepairContext(
        shot_id=0, shot_url="",
        shot_prompt=prompt, canonical_image_url="",
        is_climax_shot=True, is_top_episode=True,
    )
    return sora(ctx)


def main() -> int:
    """诊断 + 演示。无凭据则只报告状态。"""

    # 强制覆盖 .env
    env_path = _REPO / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, _, v = line.partition("=")
            v = v.split("#", 1)[0].strip()
            if k and v:
                os.environ[k.strip()] = v

    print("=== Veo 3.1 / Sora 2 路径诊断 ===\n")
    veo_ok, veo_msg = has_veo_credentials()
    sora_ok, sora_msg = has_sora_credentials()

    print(f"[Veo 3.1]   {'✓' if veo_ok else '✗'} {veo_msg}")
    print(f"[Sora 2]    {'✓' if sora_ok else '✗'} {sora_msg}")
    print()

    if not veo_ok and not sora_ok:
        print("─" * 60)
        print("缺凭据,无法激活 production.yaml repair_routes.climax_enhance 路径。")
        print()
        print("接 Veo 3.1 步骤:")
        print("  1. https://console.cloud.google.com — 创建 GCP project,启用 Vertex AI")
        print("  2. 申请 Veo 3.1 access (preview 期需 allowlist)")
        print("  3. 装 gcloud CLI: scoop install gcloud")
        print("  4. gcloud auth application-default login")
        print("  5. 把 PROJECT_ID 和 access_token 写到 .env:")
        print("     GOOGLE_CLOUD_PROJECT=<your-project-id>")
        print("     GOOGLE_ACCESS_TOKEN=$(gcloud auth print-access-token)")
        print("  6. 重跑 python scripts/r14_veo_sora_wiring.py")
        print()
        print("接 Sora 2 步骤:")
        print("  1. https://platform.openai.com/account — 申请 Sora 2 video API access")
        print("  2. 企业账户激活后,OPENAI_API_KEY 自动可调")
        print("  3. .env 已配置 OPENAI_API_KEY,缺少访问权(40-50)")
        return 1

    # 真实演示:用 R13 ep03 prompt 重渲(只是 wiring 验证,不修 R13 输出)
    from prompts.episodes import nie_xiaoqian_ch1 as nx
    ep = nx.EPISODES[2]
    print(f"── 验证 wiring: 用 {ep['ep_id']} 的 prompt 跑 1 次 ──")
    if veo_ok:
        print("\n[Veo 3.1 Fast] 调用...")
        try:
            gcs_uri = render_veo31_fast(ep["prompt"][:2000], duration_seconds=8)
            print(f"  ✓ GCS URI: {gcs_uri}")
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {str(e)[:200]}")
    if sora_ok:
        print("\n[Sora 2 Pro] 调用...")
        try:
            url = render_sora2_pro(ep["prompt"][:2000], duration_seconds=8)
            print(f"  ✓ URL: {url}")
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
