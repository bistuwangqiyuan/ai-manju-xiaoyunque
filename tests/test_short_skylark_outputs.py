"""10 项世界级母带验收测试 — Skylark Agent 2.0 + Shell 5 cinematic master.

每个测试独立断言，失败信息精确指向问题：
    1. test_three_mp4_exist_with_real_task_id    3 个 final mp4 存在 + manifest task_id 是真 UUID
    2. test_duration_per_plot_under_60s          每集 25 ≤ duration ≤ 62（剧情驱动，60s 以内）
    3. test_resolution_1080x1920_portrait        width=1080, height=1920（项目标准）
    4. test_codec_h264_yuv420p_high_profile      h264 / yuv420p / profile=High
    5. test_framerate_24fps                      r_frame_rate ∈ [23.95, 24.05]
    6. test_file_size_and_bitrate_master_grade   2MB ≤ size ≤ 250MB & bitrate ≥ 6 Mbps
    7. test_faststart_moov_before_mdat           mp4 moov 偏移 < mdat 偏移（流媒体首帧立刻可播）
    8. test_aigc_meta_tagged_true                manifest 每集 aigc_meta_tagged == True
    9. test_watermark_visible_bottom_right       右下角 ROI Y 通道 p99 ≥ 140（白@0.6 水印签名）
   10. test_metadata_title_and_comment_present   mp4 udta tags 含 title/comment + task_id 一致

前置：先 `python pilot/run_three_short_episodes.py` 跑出 manifest.json 和三个 ep0X_micro.mp4。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from src.shell5_post_production import (  # noqa: E402  module path setup above
    ffprobe_streams_format,
    is_faststart,
    sample_roi_stats,
)

ROOT = _REPO / "data" / "pilot_short_skylark"
MANIFEST = ROOT / "manifest.json"

# Skylark 2.0 真任务 id 通常是 12+ 长的 16 进制／带连字符的字符串；
# 早期占位字面量 "completed"/"skipped_existing" 必须排除。
TASK_ID_RE = re.compile(r"^[0-9a-fA-F][0-9a-fA-F-]{8,}$")

# 水印 ROI（1080×1920 母带）—— 右下角包络框，留 30px 边距 + 一定误差余量
WATERMARK_ROI = (1080 - 270, 1920 - 110, 1080 - 10, 1920 - 20)


def _episodes() -> list[dict]:
    """Read pilot manifest. Skip (not fail) when the pilot hasn't been run yet.

    Rationale: these 10 tests are real-network integration assertions on the
    Skylark master output. Without ``data/pilot_short_skylark/manifest.json``
    there's nothing to assert. We do NOT fail CI for missing fixtures because:

    - CI runs in mock mode without VOLC AK/SK by design.
    - To exercise these tests, run::

          python pilot/run_three_short_episodes.py
          pytest -q tests/test_short_skylark_outputs.py
    """
    if not MANIFEST.exists():
        pytest.skip(
            f"missing {MANIFEST}; run `python pilot/run_three_short_episodes.py` "
            "to produce the pilot manifest before this integration suite"
        )
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    eps = data.get("episodes", [])
    if not eps:
        pytest.skip("manifest has no episodes; rerun the pilot")
    return eps


# ---------------------------------------------------------------------------
# 1. 三集 mp4 存在 + task_id 是真 UUID（非字面量占位）
# ---------------------------------------------------------------------------

def test_three_mp4_exist_with_real_task_id() -> None:
    eps = _episodes()
    ok_eps = [e for e in eps if e.get("ok")]
    assert len(ok_eps) == 3, f"expected 3 successful eps, got {len(ok_eps)}: {[e.get('id') for e in eps]}"
    for ep in ok_eps:
        final = pathlib.Path(ep["final_path"])
        assert final.exists(), f"{ep['id']} final_path missing: {final}"

        tid = ep.get("task_id", "")
        assert tid not in ("", "completed", "skipped_existing"), (
            f"{ep['id']} task_id is placeholder {tid!r}; must record real Skylark task_id"
        )
        assert TASK_ID_RE.match(tid), (
            f"{ep['id']} task_id {tid!r} does not look like a Skylark task UUID"
        )


# ---------------------------------------------------------------------------
# 2. duration ≤ 60s（剧情驱动；Skylark 三个 preset：~15s/~30s/40~60s，最长 60s）
# ---------------------------------------------------------------------------

def test_duration_per_plot_under_60s() -> None:
    """每集时长按 Skylark preset + 实际剧情决定：
       - `~15s` preset  → 实测 11-17s
       - `~30s` preset  → 实测 25-35s
       - `40~60s` preset → 实测 40-60s
    本测试上限 62s（含 2s ffmpeg 测量误差）+ master `-t cap` 硬截上限。
    下限 8s 防止意外短片（Skylark 失败兜底返回值）。
    同时验证每集 duration 落在它声明的 preset 窗口内（更细粒度）。
    """

    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        dur = float(info["format"]["duration"])
        assert 8.0 <= dur <= 62.0, (
            f"{ep['id']} duration {dur:.2f}s outside global [8.0, 62.0] cap"
        )
        preset = ep.get("duration_preset_used") or ep.get("duration_preset", "")
        # 每个 Skylark preset 的实测公差窗口
        windows = {
            "～15s": (11.0, 17.0),
            "~15s": (11.0, 17.0),
            "～30s": (24.0, 35.5),
            "~30s": (24.0, 35.5),
            "40～60s": (38.0, 62.0),
            "40~60s": (38.0, 62.0),
        }
        if preset in windows:
            lo, hi = windows[preset]
            assert lo <= dur <= hi, (
                f"{ep['id']} duration {dur:.2f}s outside `{preset}` preset window [{lo}, {hi}]"
            )


# ---------------------------------------------------------------------------
# 3. 分辨率 1080×1920 竖屏（项目母带标准 production.yaml:13）
# ---------------------------------------------------------------------------

def test_resolution_1080x1920_portrait() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        vs = [s for s in info["streams"] if s.get("codec_type") == "video"]
        assert vs, f"{ep['id']} has no video stream"
        w, h = int(vs[0]["width"]), int(vs[0]["height"])
        assert (w, h) == (1080, 1920), f"{ep['id']} resolution {w}x{h} != 1080x1920"
        assert h > w, f"{ep['id']} not portrait orientation"


# ---------------------------------------------------------------------------
# 4. 编解码：h264 High profile + yuv420p（H.264 高级母带规范）
# ---------------------------------------------------------------------------

def test_codec_h264_yuv420p_high_profile() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        vs = [s for s in info["streams"] if s.get("codec_type") == "video"][0]
        assert vs["codec_name"] == "h264", f"{ep['id']} codec {vs['codec_name']} != h264"
        assert vs["pix_fmt"] == "yuv420p", f"{ep['id']} pix_fmt {vs['pix_fmt']} != yuv420p"
        profile = vs.get("profile", "")
        assert "High" in profile, f"{ep['id']} profile {profile!r} not High-class"


# ---------------------------------------------------------------------------
# 5. 帧率 24fps（项目标准 production.yaml:14）
# ---------------------------------------------------------------------------

def test_framerate_24fps() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        vs = [s for s in info["streams"] if s.get("codec_type") == "video"][0]
        rfr = vs.get("r_frame_rate", "0/1")
        num, den = rfr.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
        assert 23.95 <= fps <= 24.05, f"{ep['id']} fps {fps:.3f} != 24.0"


# ---------------------------------------------------------------------------
# 6. 文件大小 + 码率（母带级：1080p × 24fps × 15s 不应小于 6 Mbps）
# ---------------------------------------------------------------------------

def test_file_size_and_bitrate_master_grade() -> None:
    """60s 母带最坏情况 ≈ 60s × 12 Mbps × 1.25 ≈ 110 MB，250 MB 上限给压缩波动留余量。"""

    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        size = int(info["format"]["size"])
        bit_rate = int(info["format"].get("bit_rate", 0))
        assert 2_000_000 <= size <= 250_000_000, (
            f"{ep['id']} size {size} bytes outside [2 MB, 250 MB]"
        )
        assert bit_rate >= 6_000_000, (
            f"{ep['id']} bitrate {bit_rate / 1e6:.1f} Mbps < 6 Mbps master-grade threshold"
        )


# ---------------------------------------------------------------------------
# 7. faststart：moov 在 mdat 之前
# ---------------------------------------------------------------------------

def test_faststart_moov_before_mdat() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        assert is_faststart(ep["final_path"]), (
            f"{ep['id']} mp4 moov atom is NOT before mdat; "
            "add `-movflags +faststart` to ffmpeg encode"
        )


# ---------------------------------------------------------------------------
# 8. AIGC 隐式标识：Skylark 响应 aigc_meta_tagged == True
# ---------------------------------------------------------------------------

def test_aigc_meta_tagged_true() -> None:
    eps = _episodes()
    untagged = [e["id"] for e in eps if e.get("ok") and not e.get("aigc_meta_tagged")]
    assert not untagged, (
        f"AIGC implicit watermark missing on: {untagged}; "
        "check producer_id uniqueness and content_producer length ≤256 "
        "(see compliance/aigc_label_checklist.md:67-68)"
    )


# ---------------------------------------------------------------------------
# 9. AIGC 显式水印：右下角 ROI 灰度 p99 ≥ 140（"AI 生成"白@0.6 黑描边签名）
# ---------------------------------------------------------------------------

def test_watermark_visible_bottom_right() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        # 抽 t=7.5s 帧；如果遇到全黑过场则改 t=2.5s
        stats = None
        for t in (7.5, 2.5, 12.0):
            try:
                stats = sample_roi_stats(ep["final_path"], t_sec=t, roi=WATERMARK_ROI)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue
            if stats["roi_p99"] >= 140:
                break
        assert stats is not None, f"{ep['id']} could not sample ROI frame"
        assert stats["roi_p99"] >= 140, (
            f"{ep['id']} watermark not detected: roi_p99={stats['roi_p99']:.0f} "
            f"max={stats['roi_max']:.0f} mean={stats['roi_mean']:.1f}; "
            "expected white@0.6 ‘AI 生成’ overlay at bottom-right"
        )


# ---------------------------------------------------------------------------
# 附加：mp4 udta 元数据（合规建议 aigc_label_checklist.md:78-80）
# ---------------------------------------------------------------------------

def test_metadata_title_and_comment_present() -> None:
    eps = _episodes()
    for ep in (e for e in eps if e.get("ok")):
        info = ffprobe_streams_format(ep["final_path"])
        tags = (info.get("format", {}).get("tags") or {})
        # ffmpeg 默认把 -metadata title=... 写到 mov 的 ©nam，ffprobe 读出来叫 'title'
        assert "title" in tags, f"{ep['id']} mp4 metadata missing 'title'"
        assert "comment" in tags, f"{ep['id']} mp4 metadata missing 'comment'"
        assert "AI 生成" in tags["title"], (
            f"{ep['id']} title {tags['title']!r} should contain 'AI 生成'"
        )
        assert ep.get("task_id", "") in tags.get("comment", ""), (
            f"{ep['id']} comment {tags.get('comment','')!r} should include task_id"
        )
