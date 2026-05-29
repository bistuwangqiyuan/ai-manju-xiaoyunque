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
GENRE = "ancient"

# 生成参数（默认 30s 真人写实；HappyHorse 单次最长 15s，>15s 自动两段拼接）
RESOLUTION = os.environ.get("HH_RESOLUTION", "720P")
DURATION = int(os.environ.get("HH_DURATION", "30"))
SEED = int(os.environ.get("HH_SEED", "42420528"))
SEED2 = int(os.environ.get("HH_SEED2", "42420529"))  # 第 2 段不同 seed 避免重复运动
T2I_SEED = int(os.environ.get("HH_T2I_SEED", "202605291230"))  # 每次新样片请改 seed 以生成不同首帧
COVER_FRAME_T = float(os.environ.get("HH_COVER_T", "14.0"))  # 30s 视频取中段更具代表性
T2I_SIZE = os.environ.get("HH_T2I_SIZE", "720*1280")  # 9:16 竖屏与 i2v 一致
SEGMENT_MAX = 15  # HappyHorse i2v 单次时长上限

# 视觉风格：真实电影写实风（vs 上一版的 ancient_3d_guoman 国漫）
STYLE_TAG = os.environ.get("HH_STYLE_TAG", "cinema_realism")
STYLE_LABEL = os.environ.get("HH_STYLE_LABEL", "电影写实")
SUBTITLE = os.environ.get(
    "HH_SUBTITLE",
    f"汉末 196 年 · {DURATION}s · {RESOLUTION} · 真人写实"
)

# 首帧：由 t2i 实时生成（汉末曹操军中大帐场景），上传 COS 后作为 i2v 输入
# 若已有 `firstframe.jpg` 本地缓存 + 未设 FORCE_T2I=1，则跳过 t2i 复用旧首帧
DEFAULT_FALLBACK_FIRST_FRAME = (
    "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/"
    "samples/nie03_yan_chixia.jpg"
)
T2I_FIRST_FRAME_PROMPT = (
    "电影写实风格，汉末三国军中大帐内景，深夜，烛火摇曳。\n"
    "画面左侧主位：曹操，亚洲男性、约四十岁、面庞略胖，髡发束玄色武冠，\n"
    "  浓眉深目、神色沉郁；身披玄黑色金边精铁鱼鳞甲（甲片纹理清晰），\n"
    "  外披暗红色绣金虎纹斗篷；端坐于黑漆案几之后，左手按膝、右手扶剑柄。\n"
    "画面右侧客位：荀彧，亚洲男性、约三十出头、清瘦俊朗，头戴玄色文士进贤冠，\n"
    "  蓄五绺长须、眉清目秀；身着月白色丝绸长袍、青玉腰带；\n"
    "  跪坐于竹席之上，双手捧一卷竹简，目光坚定望向曹操。\n"
    "背景：帐内悬挂大幅暗红色虎纹军旗，青铜九枝灯台烛火明亮，\n"
    "  地铺青色竹席，案几上散放竹简与一柄环首刀。\n"
    "构图：9:16 竖屏，全身入画，电影感对称构图，景深自然。\n"
    "风格：电影级写实摄影（live-action cinematic photography），\n"
    "  柯达 Vision3 胶片质感、4K 高分辨率、ARRI Alexa 色彩，\n"
    "  暖橙烛光（约 2800K）与冷蓝月光（约 5600K）混合打光，\n"
    "  皮肤毛孔/胡须/铠甲鳞片/丝绸经纬/烛火光晕清晰可辨，\n"
    "  皮肤呈现真实肌理与微小油光，面部表情自然有神。"
)
T2I_NEGATIVE_PROMPT = (
    "anime, 动漫风, 卡通, cartoon, illustration, 3D 国漫, 3D 渲染卡通, "
    "二次元, painting, 油画, 水彩, 漫画线稿, 塑胶感, plastic skin, "
    "现代服装, 西装, 眼镜, 模糊, 低分辨率, 变形, 多手指, 多人头, 畸形脸, "
    "水印, 文字, logo, 中国结, 太多装饰"
)

# 视频 prompt 通用风格（每段都附加，确保两段风格一致）
COMMON_STYLE = (
    "电影写实风格、live-action cinematic photography，"
    "柯达 Vision3 胶片质感、ARRI Alexa 色彩、4K，"
    "暖橙烛光与冷蓝月光对比，皮肤毛孔、胡须、铠甲鳞片、丝绸经纬清晰可辨，"
    "面部表情自然真实，无动漫、无卡通、无 3D 国漫渲染感，无变形无走样。"
)

# 段 1（0-15s）：环境推进 → 荀彧进言
PROMPT_SEG1 = (
    "汉末 196 年深秋之夜，曹操军中大帐内。\n"
    "【0-3s】镜头从远景缓慢推近案几两侧：火光忽明忽暗，旌旗微动。\n"
    "【3-9s】曹操缓缓抬手按住下颌，眉头深锁，手指轻叩案几一次，"
    "目光沉沉地落向对面。\n"
    "【9-15s】荀彧上身微微前倾，举起双手中的竹简，张口缓缓进言，"
    "嘴唇按真人节奏开合（自然口型），眼神坚定而恳切。\n"
    + COMMON_STYLE
)

# 段 2（15-30s）：曹操凝思 → 起身允诺 → 镜头拉远定格
PROMPT_SEG2 = (
    "承接上一镜头，汉末军中大帐内，深夜烛火摇曳。\n"
    "【0-4s】曹操凝望荀彧片刻，眼神由疑虑转为坚定，嘴角微动，吐出一字。\n"
    "【4-9s】曹操缓缓推案而起，按剑直立，斗篷自然垂下；荀彧亦起身躬身行礼。\n"
    "【9-15s】镜头略微拉远，越过案几俯瞰两人全身，曹操转身面向帐门、"
    "目光投向北方；镜头自然收尾，画面渐定于两人剪影与摇曳烛火。\n"
    + COMMON_STYLE
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
    _download_with_retry(img_url, ff_local, attempts=5, label="firstframe")
    print(f"     saved {ff_local.stat().st_size / 1024:.1f} KB")
    print(f"[0d] 上传首帧到 COS：samples/{ff_local.name}")
    upload_to_cos([ff_local])
    return ff_local, cos_url


def submit_segment(first_frame_url: str, prompt: str, *,
                   duration: int, seed: int, tag: str) -> str:
    """提交一段 i2v 任务。tag 用于日志（例如 'seg1'/'seg2'）。"""
    print(f"[{tag}] 提交 HappyHorse i2v")
    print(f"    first_frame = {first_frame_url}")
    print(f"    resolution  = {RESOLUTION}  duration = {duration}s  seed = {seed}")
    print(f"    prompt[:80] = {prompt[:80].replace(chr(10), ' ')}…")
    tid = hh.submit_i2v(first_frame_url, prompt,
                        resolution=RESOLUTION, duration=int(duration),
                        watermark=False, seed=int(seed))
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


def _download_with_retry(url: str, dest: Path, *, attempts: int = 5,
                         label: str = "asset") -> None:
    """带指数退避的 URL → 本地文件下载（防 TLS 闪断 / RemoteDisconnected）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = min(30, 2 ** i)
            print(f"    [retry {i}/{attempts}] {label}: {type(e).__name__}: "
                  f"{str(e)[:80]} → wait {wait}s")
            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                pass
            time.sleep(wait)
    raise RuntimeError(f"download failed after {attempts} attempts: {last_err}")


def download(url: str, dest: Path) -> None:
    print(f"[3] 下载视频 → {dest}")
    _download_with_retry(url, dest, attempts=5, label="video")
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"    saved {size_mb:.2f} MB")


def extract_last_frame(mp4: Path, out_jpg: Path) -> bool:
    """抽取视频的最后一帧（用 -sseof -0.3 取近末尾），失败返回 False。"""
    print(f"[mid] 抽取末帧 ← ffmpeg (sseof -0.3) {mp4.name}")
    if shutil.which("ffmpeg") is None:
        print(f"    [skip] ffmpeg 不可用")
        return False
    cmd = [
        "ffmpeg", "-y", "-sseof", "-0.3", "-i", str(mp4),
        "-frames:v", "1", "-q:v", "2", str(out_jpg),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_jpg.exists():
        print(f"    ffmpeg failed: {proc.stderr[-200:]}")
        return False
    print(f"    saved {out_jpg.stat().st_size / 1024:.1f} KB")
    return True


def upload_single_to_cos(path: Path, key_name: str) -> str:
    """单文件上传到 COS samples/，返回公网 URL。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import cos_hosting_upload as cu  # type: ignore
    sid, skey = cu._get_creds()
    from qcloud_cos import CosConfig, CosS3Client  # type: ignore
    cfg = CosConfig(Region=cu.REGION, SecretId=sid, SecretKey=skey, Timeout=120)
    cli = CosS3Client(cfg)
    key = f"samples/{key_name}"
    with open(path, "rb") as f:
        data = f.read()
    ct = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
    cli.put_object(Bucket=cu.BUCKET, Key=key, Body=data, ContentType=ct,
                   CacheControl="public, max-age=86400")
    print(f"    [cos] OK {key} ({len(data)/1024:.1f} KB)")
    return f"https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/{key}"


def concat_mp4(segments: list[Path], out: Path) -> None:
    """用 ffmpeg concat demuxer 无损拼接多段 .mp4（编码相同时无重编码）。

    若直接 copy 不行（编码/容器差异），自动回退到重新编码 H.264。
    """
    print(f"[concat] 拼接 {len(segments)} 段 → {out.name}")
    out.parent.mkdir(parents=True, exist_ok=True)
    list_file = out.with_suffix(".concat.txt")
    list_file.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in segments) + "\n",
        encoding="utf-8",
    )
    cmd_copy = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(out),
    ]
    proc = subprocess.run(cmd_copy, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size < 1024:
        print(f"    [warn] -c copy 失败（{proc.returncode}），回退到重新编码 H.264")
        cmd_enc = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out),
        ]
        proc = subprocess.run(cmd_enc, capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"concat failed: {proc.stderr[-300:]}")
    list_file.unlink(missing_ok=True)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"    [concat] saved {size_mb:.2f} MB")


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

        # 计算分段：HappyHorse 单次 ≤15s，DURATION>15 时拆 2 段拼接
        if DURATION <= SEGMENT_MAX:
            tid = submit_segment(first_frame_url, PROMPT_SEG1,
                                 duration=DURATION, seed=SEED, tag="seg1")
            url = poll(tid, timeout_s=900)
            download(url, mp4)
        else:
            seg1_d = SEGMENT_MAX
            seg2_d = max(3, min(SEGMENT_MAX, DURATION - SEGMENT_MAX))
            print(f"[plan] 两段拼接：seg1={seg1_d}s + seg2={seg2_d}s = {seg1_d+seg2_d}s")
            seg1_mp4 = SAMPLES_DIR / f"{SLUG}_seg1.mp4"
            seg2_mp4 = SAMPLES_DIR / f"{SLUG}_seg2.mp4"
            mid_jpg_local = SAMPLES_DIR / f"{SLUG}_midframe.jpg"

            tid1 = submit_segment(first_frame_url, PROMPT_SEG1,
                                  duration=seg1_d, seed=SEED, tag="seg1")
            url1 = poll(tid1, timeout_s=900)
            download(url1, seg1_mp4)

            print(f"[mid] 抽段1末帧 → 上传 COS → 作为段2 首帧")
            if not extract_last_frame(seg1_mp4, mid_jpg_local):
                raise RuntimeError("无法抽取段1末帧，无法续接段2")
            mid_url = upload_single_to_cos(mid_jpg_local, mid_jpg_local.name)

            tid2 = submit_segment(mid_url, PROMPT_SEG2,
                                  duration=seg2_d, seed=SEED2, tag="seg2")
            url2 = poll(tid2, timeout_s=900)
            download(url2, seg2_mp4)

            concat_mp4([seg1_mp4, seg2_mp4], mp4)

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
        "style": STYLE_TAG,
        "style_label": STYLE_LABEL,
        "video_url": f"/samples/{mp4.name}?v={cache_v}",
        "cover_url": f"/samples/{jpg.name}?v={cache_v}",
        "quality_score": 96,
        "episodes": 1,
        "author_label": f"官方示例 · HappyHorse 真实生成 · {DURATION}s",
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
