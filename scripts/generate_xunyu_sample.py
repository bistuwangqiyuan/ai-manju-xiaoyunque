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
SLIM_SCF_DIR = ROOT / "deploy" / "cloudfn-slim"
SLUG = "xunyu_yingxiandi"
TITLE = "荀彧劝曹操迎献帝"
SUBTITLE = "汉末 196 年 · 15s · 720P 真实生成"
GENRE = "ancient"

# 生成参数（15s + 720P + 关水印 + 固定 seed 便于复现）
RESOLUTION = os.environ.get("HH_RESOLUTION", "720P")
DURATION = int(os.environ.get("HH_DURATION", "15"))
SEED = int(os.environ.get("HH_SEED", "42420528"))
T2I_SEED = int(os.environ.get("HH_T2I_SEED", "20260528"))
COVER_FRAME_T = float(os.environ.get("HH_COVER_T", "7.0"))  # 15s 视频取中段更具代表性
T2I_SIZE = os.environ.get("HH_T2I_SIZE", "720*1280")  # 9:16 竖屏与 i2v 一致

# 首帧：由 t2i 实时生成（汉末曹操军中大帐场景），上传 COS 后作为 i2v 输入
# 若已有 `firstframe.jpg` 本地缓存 + 未设 FORCE_T2I=1，则跳过 t2i 复用旧首帧
DEFAULT_FALLBACK_FIRST_FRAME = (
    "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/"
    "samples/nie03_yan_chixia.jpg"
)
T2I_FIRST_FRAME_PROMPT = (
    "汉末三国时期，曹操军中大帐内景，深夜，烛火摇曳。\n"
    "画面左侧主位：曹操，约四十岁，髡发束冠，浓眉锐目，神色沉郁；\n"
    "  身披玄黑色金边精铁甲胄（鱼鳞甲片清晰），披风暗红色绣金虎纹；\n"
    "  端坐于黑漆案几之后，左手按膝、右手扶剑柄。\n"
    "画面右侧客位：荀彧，约三十出头，头戴玄色文士进贤冠，面容俊朗，\n"
    "  五绺长须，眉清目秀；身着月白色丝绸长袍、青玉腰带；\n"
    "  跪坐于竹席之上，双手捧一卷竹简，目光坚定地望向曹操。\n"
    "背景：帐内悬挂大幅虎纹军旗，青铜九枝灯台烛火明亮，\n"
    "  地铺青色竹席，案几上散放竹简与一柄环首刀。\n"
    "构图：9:16 竖屏，全景含两人完整身体，电影感对称构图。\n"
    "风格：古风3D国漫、电影级光影，墨黑/暖橙烛光/月白为主色调，\n"
    "  质感细腻：发丝、铠甲鳞片、布料纹理、烛火光晕清晰可辨，\n"
    "  面部表情自然有神，无变形无走样，整体沉稳大气。"
)
T2I_NEGATIVE_PROMPT = (
    "现代服装, 西装, 眼镜, 卡通风格, 模糊, 低分辨率, 变形, 多手指, 多人头, "
    "畸形脸, 水印, 文字, logo, 中国结, 太多装饰"
)

# 三幕式 prompt（每幕 ~5s）以最大化 15s 内的视觉信息密度
PROMPT = (
    "汉末 196 年深秋之夜，曹操军中大帐外旌旗猎猎、远处烽火明灭。\n"
    "【第一幕 0-5s】镜头从帐外远景缓推：黑色玄甲铁骑列阵肃立，士卒铠甲映着篝火"
    "暖橙，旌旗在夜风中翻卷，帐帘被风吹起，露出帐内昏黄烛光。\n"
    "【第二幕 5-10s】镜头切入帐内：曹操披玄色金边甲胄端坐主位案前，眉头深锁、"
    "手指轻叩案几。荀彧着月白色文士长袍跪坐对面，手抚长卷，目光清澈而坚定，"
    "举袂进言：「奉天子以令不臣，秉至公以服雄杰，扶弘义以致英俊，"
    "此乃霸王之业也，明公何疑？」\n"
    "【第三幕 10-15s】曹操缓缓抬眼，眸光骤亮，旋即起身按剑、回望帐外北方，"
    "镜头从他的背影越过帐帘升向夜空——明月一轮、群星如棋。\n"
    "视觉风格：古风3D国漫，电影级光影，9:16 竖屏短剧，质感细腻，"
    "烛火与盔甲反光柔和自然，发丝、布料、金属纹理清晰可辨，"
    "面部表情自然，无变形无走样，色调以墨黑、暖橙烛光、月白为主，沉稳大气。"
)


def gen_first_frame() -> tuple[Path, str]:
    """先用 DashScope WanX 文生图生成一张「汉末曹操军中大帐」首帧。

    成功后下载到本地、上传到 COS，返回 (本地 jpg path, 公网 url)。
    若 t2i 失败，则回退到 DEFAULT_FALLBACK_FIRST_FRAME（远端 URL，本地 path 返回 None）。
    """
    ff_local = SAMPLES_DIR / f"{SLUG}_firstframe.jpg"
    cos_url = (
        f"https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/"
        f"samples/{ff_local.name}"
    )
    if ff_local.exists() and os.environ.get("FORCE_T2I") != "1":
        print(f"[0a] 复用首帧缓存：{ff_local}（如需重新生成请设 FORCE_T2I=1）")
        return ff_local, cos_url
    print(f"[0a] 提交 DashScope WanX 文生图（{T2I_SIZE}, seed={T2I_SEED}）")
    print(f"     prompt[:80] = {T2I_FIRST_FRAME_PROMPT[:80].replace(chr(10), ' ')}…")
    try:
        tid, used_model = hh.submit_t2i(
            T2I_FIRST_FRAME_PROMPT,
            size=T2I_SIZE, n=1, seed=T2I_SEED,
            negative_prompt=T2I_NEGATIVE_PROMPT,
        )
    except hh.HappyHorseError as e:
        print(f"     [WARN] 文生图提交失败：{e}；回退到默认首帧")
        return ff_local, DEFAULT_FALLBACK_FIRST_FRAME
    print(f"     task_id={tid} model={used_model}")
    print(f"[0b] 轮询文生图（最多 240s）")
    start = time.time()
    img_url = ""
    while time.time() - start < 240:
        out = hh.query(tid)
        status = (out.get("task_status") or "").upper()
        if status == hh.STATUS_SUCCEEDED:
            results = out.get("results") or []
            img_url = (results[0] or {}).get("url") if results else ""
            if not img_url:
                print(f"     [WARN] SUCCEEDED 但 url 为空：{out}")
                return ff_local, DEFAULT_FALLBACK_FIRST_FRAME
            print(f"     ok t={int(time.time()-start)}s url[:90]={img_url[:90]}")
            break
        if status in hh.TERMINAL_FAIL:
            print(f"     [WARN] terminal={status} msg={out.get('message') or out.get('code')}")
            return ff_local, DEFAULT_FALLBACK_FIRST_FRAME
        print(f"     [{int(time.time()-start):>3}s] status={status}")
        time.sleep(8)
    if not img_url:
        print(f"     [WARN] t2i 超时，回退")
        return ff_local, DEFAULT_FALLBACK_FIRST_FRAME
    print(f"[0c] 下载首帧 → {ff_local}")
    ff_local.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(img_url, timeout=120) as resp, open(ff_local, "wb") as f:
        shutil.copyfileobj(resp, f)
    print(f"     saved {ff_local.stat().st_size / 1024:.1f} KB")
    print(f"[0d] 上传首帧到 COS：samples/{ff_local.name}")
    upload_to_cos([ff_local])
    return ff_local, cos_url


def submit(first_frame_url: str) -> str:
    print(f"[1] 提交 HappyHorse i2v 任务")
    print(f"    first_frame = {first_frame_url}")
    print(f"    resolution  = {RESOLUTION}  duration = {DURATION}s  seed = {SEED}")
    print(f"    prompt[:80] = {PROMPT[:80].replace(chr(10), ' ')}…")
    tid = hh.submit_i2v(first_frame_url, PROMPT,
                        resolution=RESOLUTION, duration=DURATION,
                        watermark=False, seed=SEED)
    print(f"    task_id     = {tid}")
    return tid


def poll(task_id: str, timeout_s: int = 900) -> str:
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
    """用 ffmpeg 在 ``COVER_FRAME_T`` 秒处抽一帧作为封面。失败返回 False。"""
    print(f"[4] 抽取封面 ← ffmpeg (t={COVER_FRAME_T}s)")
    if shutil.which("ffmpeg") is None:
        print(f"    [skip] ffmpeg 不可用，复用首帧作为封面")
        return False
    cmd = [
        "ffmpeg", "-y", "-ss", str(COVER_FRAME_T), "-i", str(mp4),
        "-frames:v", "1", "-q:v", "2", str(cover),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not cover.exists():
        print(f"    ffmpeg failed: {proc.stderr[-200:]}")
        return False
    print(f"    saved {cover.stat().st_size / 1024:.1f} KB")
    return True


def reuse_first_frame_as_cover_remote(url: str, cover: Path) -> None:
    print(f"[4b] 下载首帧作为封面 → {cover}")
    with urllib.request.urlopen(url, timeout=60) as resp, open(cover, "wb") as f:
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
        first_frame_local = SAMPLES_DIR / f"{SLUG}_firstframe.jpg"
        first_frame_url = (
            f"https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/"
            f"samples/{first_frame_local.name}"
            if first_frame_local.exists() else DEFAULT_FALLBACK_FIRST_FRAME
        )
    else:
        first_frame_local, first_frame_url = gen_first_frame()
        tid = submit(first_frame_url)
        url = poll(tid, timeout_s=900)
        download(url, mp4)
        if not extract_cover(mp4, jpg):
            print(f"     [fallback] 改用首帧图作为封面")
            if first_frame_local.exists():
                shutil.copyfile(first_frame_local, jpg)
            else:
                reuse_first_frame_as_cover_remote(first_frame_url, jpg)

    upload_to_cos([mp4, jpg])

    # 拼接版本号 querystring 强制 CDN 重新拉取（覆盖旧版同名文件）
    cache_v = os.environ.get("HH_CACHE_V") or time.strftime("%Y%m%d%H%M")
    sample = {
        "id": f"sample-{SLUG}",
        "kind": "official",
        "title": TITLE,
        "subtitle": SUBTITLE,
        "genre": GENRE,
        "style": "ancient_3d_guoman",
        "video_url": f"/samples/{mp4.name}?v={cache_v}",
        "cover_url": f"/samples/{jpg.name}?v={cache_v}",
        "quality_score": 96,
        "episodes": 1,
        "author_label": "官方示例 · HappyHorse 真实生成",
        "slug": SLUG,
    }
    print(f"[6] 更新 catalog.json")
    update_catalog(SAMPLES_DIR / "catalog.json", sample)
    update_catalog(CFN_SAMPLES_DIR / "catalog.json", sample)
    update_catalog(SLIM_SCF_DIR / "catalog.json", sample)
    print(f"\nDone. 新示例：{TITLE}")
    print(f"  video: https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/{mp4.name}")
    print(f"  cover: https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/{jpg.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
