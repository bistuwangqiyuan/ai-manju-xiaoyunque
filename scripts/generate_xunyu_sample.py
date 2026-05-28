"""端到端生成「荀彧劝曹操迎献帝」示例视频，并上传到 CloudBase 静态托管。

流程：
  1. 调用阿里 HappyHorse i2v 提交任务（720P, 5s, 无水印）
  2. 轮询任务状态，等待 SUCCEEDED
  3. 下载 .mp4 到本地 web/public/samples/
  4. 用 ffmpeg 抽取第 1.0s 的帧作为 cover.jpg（若 ffmpeg 不可用则复用 first_frame）
  5. 把 .mp4 + .jpg 通过 cos_hosting_upload 上传到 CloudBase Hosting
  6. 更新 web/public/samples/catalog.json，把新示例加到 list 头部
  7. 同步更新 cloudfunctions/xyq-api/web/public/samples/catalog.json（如果存在）

环境变量：
  HAPPYHORSE_API_KEY   阿里百炼 API Key（已注入 SCF；本地需手动 export）
  TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY  腾讯云 AKSK（用于 COS 直传）

运行：
  $env:HAPPYHORSE_API_KEY='sk-...'; python scripts/generate_xunyu_sample.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "deploy" / "cloudfn-slim"))

import happyhorse_client as hh  # noqa: E402

SAMPLES_DIR = ROOT / "web" / "public" / "samples"
CFN_SAMPLES_DIR = ROOT / "cloudfunctions" / "xyq-api" / "web" / "public" / "samples"
SLUG = "xunyu_yingxiandi"
TITLE = "荀彧劝曹操迎献帝"
SUBTITLE = "汉末 196 年 · 谋士定鼎大局的关键一夜"
GENRE = "ancient"

# 首帧：选用现有古风男子样片作为视觉起点，prompt 驱动汉末三国意境
FIRST_FRAME_URL = (
    "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/"
    "samples/nie03_yan_chixia.jpg"
)

PROMPT = (
    "汉末 196 年的将军大帐内，烛火摇曳。曹操披玄色甲胄端坐主位，神情沉吟。"
    "荀彧着月白色文士长袍跪坐对面，手抚案几，目光坚定地进言："
    "「奉天子以令诸侯，乃霸王之业也。」镜头从二人的对视缓缓推近，"
    "帐外可见远山影影绰绰的旌旗轮廓。古风3D国漫风格，9:16 竖屏短剧，"
    "电影感光影，质感细腻，烛火与盔甲反光柔和自然，无变形无走样。"
)


def submit() -> str:
    print(f"[1] 提交 HappyHorse i2v 任务")
    print(f"    first_frame = {FIRST_FRAME_URL}")
    print(f"    prompt[:80] = {PROMPT[:80]}…")
    tid = hh.submit_i2v(FIRST_FRAME_URL, PROMPT,
                        resolution="720P", duration=5, watermark=False)
    print(f"    task_id     = {tid}")
    return tid


def poll(task_id: str, timeout_s: int = 600) -> str:
    print(f"[2] 轮询任务状态（最多 {timeout_s}s，每 15s 查询一次）")
    start = time.time()
    last_status = ""
    while time.time() - start < timeout_s:
        out = hh.query(task_id)
        status = (out.get("task_status") or "").upper()
        if status != last_status:
            elapsed = int(time.time() - start)
            print(f"    [{elapsed:>3}s] status={status}")
            last_status = status
        if status == hh.STATUS_SUCCEEDED:
            video_url = out.get("video_url") or ""
            if not video_url:
                raise RuntimeError(f"SUCCEEDED 但 video_url 为空：{out}")
            print(f"    video_url = {video_url[:90]}…")
            return video_url
        if status in hh.TERMINAL_FAIL:
            raise RuntimeError(f"任务失败 status={status} msg={out.get('message') or out.get('code')}")
        time.sleep(15)
    raise TimeoutError(f"轮询超时（>{timeout_s}s）")


def download(url: str, dest: Path) -> None:
    print(f"[3] 下载视频 → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"    saved {size_mb:.2f} MB")


def extract_cover(mp4: Path, cover: Path) -> bool:
    """用 ffmpeg 抽取第 1.0s 的帧作为封面。失败则返回 False。"""
    print(f"[4] 抽取封面 ← ffmpeg")
    if shutil.which("ffmpeg") is None:
        print(f"    [skip] ffmpeg 不可用，复用首帧作为封面")
        return False
    cmd = [
        "ffmpeg", "-y", "-ss", "1.0", "-i", str(mp4),
        "-frames:v", "1", "-q:v", "2", str(cover),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not cover.exists():
        print(f"    ffmpeg failed: {proc.stderr[-200:]}")
        return False
    print(f"    saved {cover.stat().st_size / 1024:.1f} KB")
    return True


def reuse_first_frame_as_cover(cover: Path) -> None:
    print(f"[4b] 下载首帧作为封面 → {cover}")
    with urllib.request.urlopen(FIRST_FRAME_URL, timeout=60) as resp, open(cover, "wb") as f:
        shutil.copyfileobj(resp, f)


def upload_to_cos(local_paths: list[Path]) -> None:
    print(f"[5] 上传 {len(local_paths)} 个文件到 CloudBase Hosting (COS)")
    sys.path.insert(0, str(ROOT / "scripts"))
    import cos_hosting_upload as cu  # type: ignore
    sid, skey = cu._get_creds()
    if not sid or not skey:
        raise RuntimeError("缺少 TENCENTCLOUD_SECRET_ID/SECRET_KEY")
    from qcloud_cos import CosConfig, CosS3Client  # type: ignore
    cfg = CosConfig(Region=cu.REGION, SecretId=sid, SecretKey=skey, Timeout=120)
    cli = CosS3Client(cfg)
    for path in local_paths:
        key = f"samples/{path.name}"
        with open(path, "rb") as f:
            data = f.read()
        ct = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
        cli.put_object(Bucket=cu.BUCKET, Key=key, Body=data, ContentType=ct,
                       CacheControl="public, max-age=86400")
        print(f"    OK {key} ({len(data)/1024:.1f} KB)")


def update_catalog(catalog_path: Path, sample: dict) -> None:
    if not catalog_path.exists():
        print(f"    [skip] {catalog_path} 不存在")
        return
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    samples = data.get("samples") or []
    samples = [s for s in samples if s.get("id") != sample["id"]]
    samples.insert(0, sample)  # 新示例置顶
    data["samples"] = samples
    catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    print(f"    更新 {catalog_path.relative_to(ROOT)} (now {len(samples)} samples)")


def main() -> int:
    if not hh.is_configured():
        print("FAIL: HAPPYHORSE_API_KEY/DASHSCOPE_API_KEY 环境变量未设置")
        return 1

    mp4 = SAMPLES_DIR / f"{SLUG}.mp4"
    jpg = SAMPLES_DIR / f"{SLUG}.jpg"

    if mp4.exists() and os.environ.get("FORCE") != "1":
        print(f"[skip-gen] {mp4} 已存在，跳过生成；如需重新生成请设 FORCE=1")
    else:
        tid = submit()
        url = poll(tid, timeout_s=600)
        download(url, mp4)
        if not extract_cover(mp4, jpg):
            reuse_first_frame_as_cover(jpg)

    upload_to_cos([mp4, jpg])

    sample = {
        "id": f"sample-{SLUG}",
        "kind": "official",
        "title": TITLE,
        "subtitle": SUBTITLE,
        "genre": GENRE,
        "style": "ancient_3d_guoman",
        "video_url": f"/samples/{mp4.name}",
        "cover_url": f"/samples/{jpg.name}",
        "quality_score": 96,
        "episodes": 1,
        "author_label": "官方示例 · HappyHorse 真实生成",
        "slug": SLUG,
    }
    print(f"[6] 更新 catalog.json")
    update_catalog(SAMPLES_DIR / "catalog.json", sample)
    update_catalog(CFN_SAMPLES_DIR / "catalog.json", sample)
    print(f"\nDone. 新示例：{TITLE}")
    print(f"  video: https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/{mp4.name}")
    print(f"  cover: https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/{jpg.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
