"""V10 footprint model — container image size + cold-start estimation.

Inputs: dependency closure (PIP wheels + system libs + font/BGM assets).
Output: per-layer size, total ROM after decompression, and cold-start
time estimate (linear regression on prior measurements).

Decision rule emitted: whether to split off ``xyq-av-worker``.

Run::

    python -m tools.data_models.footprint_model
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from tools.data_models._common import (
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)


# ---------------------------------------------------------------------------
# Layer sizing (MB after decompression).  Numbers are conservative upper
# bounds based on PyPI wheel listings (2026-05).
# ---------------------------------------------------------------------------
PIP_PKG_MB = {
    # base
    "python_base": 90,
    "fastapi+uvicorn+pydantic+sqlalchemy": 50,
    "boto3+aws-cli stubs": 25,
    "yaml+jinja2+jose+passlib": 18,
    # v9 existing
    "anthropic+openai+google_genai sdks": 65,
    "insightface+onnxruntime": 280,
    "pillow": 12,
    # v10 P3 (text)
    "python-docx": 4,
    "pypdf": 3,
    "langdetect": 2,
    "networkx": 6,
    # v10 P4 (vision)
    "mediapipe": 30,
    "ultralytics": 75,           # includes weights
    "open_clip_torch": 1_900,    # bundled torch
    "faiss-cpu": 45,
    "imagehash": 1,
    # v10 P6
    "opencv-python": 65,
    "pytorch-grad-cam": 6,
    # v10 P7 (audio)
    "whisperx": 130,
    "pyannote-audio": 65,
    "librosa": 30,
    "laion-clap": 1_700,         # bundled torch+model
    "pyloudnorm": 1,
    "pedalboard": 20,
    # v10 P8 (derivative)
    "reportlab": 30,
    "scenedetect": 8,
    "paddleocr": 320,            # includes paddlepaddle base
    "paddlepaddle": 380,
    "moviepy": 12,
    "controlnet-aux": 70,
    # v10 P9
    "apscheduler": 4,
    "websockets": 2,
    # v10 P11
    "slowapi": 2,
    "authlib": 5,
    "alembic": 6,
}

SYSTEM_LIB_MB = {
    "ffmpeg static (full)": 95,
    "fonts (Source Han Sans+Serif+Kai+Yuan + 篆书替代)": 80,
    "Caddy binary": 40,
    "node_modules (next.js standalone)": 220,
    "next.js .next + public": 60,
}

STATIC_ASSET_MB = {
    "data/bgm_library (50 CC0 tracks)": 250,
    "data/sfx_library (100 effects)":   50,
    "config/genres/style_anchor (5 imgs)": 5,
}


@dataclass
class ImageVariant:
    name: str
    pip_groups: list[str]
    system_libs: list[str]
    static_assets: list[str]
    expected_cold_start_s_per_gb: float = 1.3   # measured on veFaaS cn-beijing
    base_cold_start_s: float = 1.8


VARIANTS = [
    ImageVariant(
        name="v9_current",
        pip_groups=[
            "python_base", "fastapi+uvicorn+pydantic+sqlalchemy",
            "boto3+aws-cli stubs", "yaml+jinja2+jose+passlib",
            "anthropic+openai+google_genai sdks", "insightface+onnxruntime",
            "pillow",
        ],
        system_libs=["ffmpeg static (full)", "Caddy binary",
                     "node_modules (next.js standalone)", "next.js .next + public",
                     "fonts (Source Han Sans+Serif+Kai+Yuan + 篆书替代)"],
        static_assets=[],
    ),
    ImageVariant(
        name="v10_main_monolith",
        pip_groups=list(PIP_PKG_MB.keys()),  # everything in one image
        system_libs=list(SYSTEM_LIB_MB.keys()),
        static_assets=list(STATIC_ASSET_MB.keys()),
    ),
    ImageVariant(
        name="v10_main_lean",
        pip_groups=[
            "python_base", "fastapi+uvicorn+pydantic+sqlalchemy",
            "boto3+aws-cli stubs", "yaml+jinja2+jose+passlib",
            "anthropic+openai+google_genai sdks", "insightface+onnxruntime",
            "pillow", "python-docx", "pypdf", "langdetect", "networkx",
            "mediapipe", "ultralytics", "open_clip_torch", "faiss-cpu",
            "imagehash", "opencv-python", "pytorch-grad-cam", "reportlab",
            "scenedetect", "apscheduler", "websockets", "slowapi", "authlib",
            "alembic",
        ],
        system_libs=list(SYSTEM_LIB_MB.keys()),
        static_assets=["config/genres/style_anchor (5 imgs)"],
    ),
    ImageVariant(
        name="v10_av_worker",
        pip_groups=[
            "python_base", "fastapi+uvicorn+pydantic+sqlalchemy",
            "whisperx", "pyannote-audio", "librosa", "laion-clap",
            "pyloudnorm", "pedalboard", "paddleocr", "paddlepaddle",
            "moviepy", "controlnet-aux",
        ],
        system_libs=["ffmpeg static (full)"],
        static_assets=["data/bgm_library (50 CC0 tracks)",
                       "data/sfx_library (100 effects)",
                       "config/genres/style_anchor (5 imgs)"],
    ),
]


def derive(v: ImageVariant) -> dict:
    pip_mb  = sum(PIP_PKG_MB[k] for k in v.pip_groups)
    sys_mb  = sum(SYSTEM_LIB_MB[k] for k in v.system_libs)
    asset_mb = sum(STATIC_ASSET_MB[k] for k in v.static_assets)
    total_mb = pip_mb + sys_mb + asset_mb
    total_gb = total_mb / 1024
    cold_start = v.base_cold_start_s + total_gb * v.expected_cold_start_s_per_gb
    return {
        "variant": asdict(v),
        "pip_mb": pip_mb,
        "system_mb": sys_mb,
        "asset_mb": asset_mb,
        "total_mb": total_mb,
        "total_gb": round(total_gb, 2),
        "cold_start_s_estimated": round(cold_start, 1),
        "exceeds_vefaas_2gb_limit": total_mb > 2 * 1024,
        "exceeds_vefaas_8gb_limit": total_mb > 8 * 1024,
    }


def build_report() -> dict:
    derived = [derive(v) for v in VARIANTS]
    # Decision
    monolith = next(d for d in derived if d["variant"]["name"] == "v10_main_monolith")
    lean = next(d for d in derived if d["variant"]["name"] == "v10_main_lean")
    av_worker = next(d for d in derived if d["variant"]["name"] == "v10_av_worker")
    decision = {
        "monolith_total_gb": monolith["total_gb"],
        "monolith_cold_start_s": monolith["cold_start_s_estimated"],
        "monolith_exceeds_8gb": monolith["exceeds_vefaas_8gb_limit"],
        "split_main_total_gb": lean["total_gb"],
        "split_av_total_gb": av_worker["total_gb"],
        "split_main_cold_start_s": lean["cold_start_s_estimated"],
        "split_av_cold_start_s": av_worker["cold_start_s_estimated"],
        "recommend_split": monolith["exceeds_vefaas_8gb_limit"] or monolith["cold_start_s_estimated"] > 15,
        "reasoning": (
            "monolith 镜像超 8GB 或冷启动 >15s → 拆分 av_worker"
            if (monolith["exceeds_vefaas_8gb_limit"] or monolith["cold_start_s_estimated"] > 15)
            else "monolith 在 veFaaS 限制内"
        ),
    }
    return {
        "model": "footprint_model",
        "version": "v10.0",
        "pip_pkg_mb": PIP_PKG_MB,
        "system_lib_mb": SYSTEM_LIB_MB,
        "static_asset_mb": STATIC_ASSET_MB,
        "variants": derived,
        "decision": decision,
    }


def render_markdown(report: dict) -> str:
    parts = [
        "# 容器足迹模型 (footprint_model)",
        "",
        "> 4 个镜像变体 × (PIP + 系统库 + 静态资产) → 总大小 + 冷启动 + 拆分决策",
        "",
        "## 1. 四档镜像变体",
        "",
        render_table(
            ["变体", "PIP MB", "系统 MB", "资产 MB", "总 GB", "冷启动 s", "超 8GB"],
            [
                [
                    d["variant"]["name"],
                    d["pip_mb"],
                    d["system_mb"],
                    d["asset_mb"],
                    d["total_gb"],
                    d["cold_start_s_estimated"],
                    "❌" if d["exceeds_vefaas_8gb_limit"] else "✅",
                ]
                for d in report["variants"]
            ],
        ),
        "",
        "## 2. 拆分决策",
        "",
        f"- monolith: **{report['decision']['monolith_total_gb']} GB** · 冷启动 {report['decision']['monolith_cold_start_s']}s",
        f"- split main: {report['decision']['split_main_total_gb']} GB · 冷启动 {report['decision']['split_main_cold_start_s']}s",
        f"- split av_worker: {report['decision']['split_av_total_gb']} GB · 冷启动 {report['decision']['split_av_cold_start_s']}s",
        f"- **推荐：{'拆分' if report['decision']['recommend_split'] else '保持单镜像'}** — {report['decision']['reasoning']}",
        "",
        "## 3. 复现",
        "",
        "```bash",
        "python -m tools.data_models.footprint_model",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("footprint_model", report)
    write_markdown("footprint_model", render_markdown(report))
    d = report["decision"]
    print(f"monolith={d['monolith_total_gb']:.1f}GB cold={d['monolith_cold_start_s']:.1f}s "
          f"split={d['recommend_split']}")
    return report


if __name__ == "__main__":
    main()
