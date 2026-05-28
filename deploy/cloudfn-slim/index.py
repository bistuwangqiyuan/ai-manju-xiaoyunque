"""Event-type CloudBase HTTP handler for xyq-api (FastAPI-lite shim).

CloudBase BaaS HTTP 访问服务要求 Event 型函数 + index.main_handler。
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import pathlib
import re
import secrets
import sqlite3
import time
from typing import Any

_DB = "/tmp/xyq_event.db"
_CATALOG = pathlib.Path(__file__).with_name("catalog.json")

_log = logging.getLogger(__name__)

try:
    import real_jobs  # type: ignore[import-not-found]
except ImportError:  # 兼容打包前的本地静态分析
    real_jobs = None  # type: ignore[assignment]

FREE_DAILY_QUOTA = 3
EPISODE_BASE_COST_CENTS = 6500
PROFIT_MULTIPLIER = 1.10
SIGNUP_BONUS_CENTS = 10000
MOCK_RENDER_SECONDS = 25


def _user_id(email: str) -> int:
    """Deterministic user id derived from email (stateless auth)."""
    h = hashlib.sha256(email.lower().strip().encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def _pwd_hash(email: str, password: str) -> str:
    return hashlib.sha256(f"{email.lower().strip()}::{password}".encode("utf-8")).hexdigest()

_GENRES = [
    {
        "id": "ancient",
        "name_zh": "古风",
        "name_en": "Ancient Chinese",
        "description": "古代中国仙侠/古言/历史/志怪",
        "style_id": "ancient_3d_guoman",
        "aspect_ratio": "9:16",
        "default_episodes": 10,
        "sample_themes": ["聊斋·聂小倩", "山雨欲来"],
        "preview_video_url": "/samples/nie01_lanruosi.mp4",
        "preview_cover_url": "/samples/nie01_lanruosi.jpg",
    },
    {
        "id": "modern",
        "name_zh": "现代",
        "name_en": "Modern",
        "description": "都市/职场/校园/家庭",
        "style_id": "modern_cinematic",
        "aspect_ratio": "9:16",
        "default_episodes": 10,
        "sample_themes": ["霸总隐婚", "高考重生"],
    },
    {
        "id": "sweet_pet",
        "name_zh": "甜宠",
        "name_en": "Sweet Romance",
        "description": "甜宠/校园爱情/年下/契约婚",
        "style_id": "sweet_anime_3d",
        "aspect_ratio": "9:16",
        "default_episodes": 8,
        "sample_themes": ["契约 100 天", "校园甜剧"],
    },
    {
        "id": "suspense",
        "name_zh": "悬疑",
        "name_en": "Suspense",
        "description": "悬疑/推理/惊悚/犯罪",
        "style_id": "noir_cinematic",
        "aspect_ratio": "9:16",
        "default_episodes": 12,
        "sample_themes": ["连环密码", "深夜地铁"],
    },
    {
        "id": "xuanhuan",
        "name_zh": "玄幻",
        "name_en": "Xuanhuan",
        "description": "玄幻/修仙/异世/魔法",
        "style_id": "xuanhuan_epic",
        "aspect_ratio": "9:16",
        "default_episodes": 12,
        "sample_themes": ["仙尊重生", "末法时代"],
        "preview_video_url": "/samples/xiyou01_immortal_stone.mp4",
        "preview_cover_url": "/samples/xiyou01_immortal_stone.jpg",
    },
]

_PLANS = {
    "starter": 9900,
    "series": 129900,
}

# ---------------------------------------------------------------------------
# 资产库样本：角色 / 场景 / 表情 / 动作 / 服饰
# 来源：prompts/characters/*.yaml + prompts/scenes/*.yaml 精简版
# ---------------------------------------------------------------------------
_LIBRARY_CHARACTERS = [
    {
        "char_id": "nie_xiaoqian",
        "name_zh": "聂小倩",
        "role": "女主角",
        "age": 18,
        "canonical_image_url": "/samples/nie02_appears.jpg",
        "signature_marks": [
            "★ 眉间一点朱砂痣（圆点直径 3mm，#C5283D，每镜可见）",
            "★ 左肩黑色藤纹束缚标记（visibility 见 episode_visibility_map）",
            "颈侧左下 0.5cm 一颗黑色小痣（与右脸颊酒窝呼应）",
        ],
        "voice": "鬼魅期清冷空灵女音 + reverb 0.2；人化期温暖少女音",
    },
    {
        "char_id": "ningcaichen",
        "name_zh": "宁采臣",
        "role": "男主角",
        "age": 22,
        "canonical_image_url": "/samples/nie01_lanruosi.jpg",
        "signature_marks": [
            "★ 长袍配青衣襦，腰束玉佩，挂书袋",
            "★ 眉清目秀，鬓发束玉冠，眼神温润如玉",
            "右手执卷不离身（赴试书生标志）",
        ],
        "voice": "温润沉稳书生音，咬字清晰",
    },
    {
        "char_id": "yan_chixia",
        "name_zh": "燕赤霞",
        "role": "侠客 / 配角",
        "age": 38,
        "canonical_image_url": "/samples/nie03_yan_chixia.jpg",
        "signature_marks": [
            "★ 短须，眉骨高耸，眼神锐利如鹰",
            "★ 腰间一柄长剑，剑鞘饰朱砂符箓",
            "右手食指带骨戒，赤红色道袍",
        ],
        "voice": "豪迈低音，气沉丹田",
    },
    {
        "char_id": "popo_yaowu",
        "name_zh": "婆婆姥姥",
        "role": "反派 / 千年树妖",
        "age": 1000,
        "canonical_image_url": None,
        "signature_marks": [
            "★ 银白长发披散过腰，皮肤如树皮皲裂",
            "★ 右手抓握黑色藤条作鞭",
            "出场时背景必有兰若寺白杨树枯影",
        ],
        "voice": "嘶哑老妇音 + 风过枯枝混响",
    },
    {
        "char_id": "ningmu_hengniang",
        "name_zh": "宁母 / 衡娘",
        "role": "宁采臣母亲",
        "age": 50,
        "canonical_image_url": None,
        "signature_marks": [
            "★ 中年妇人，髻发挽于脑后，鬓边一支素银簪",
            "★ 灰布长衫，腰系青色围裙",
            "眼角细纹与慈祥微笑共存",
        ],
        "voice": "中年妇人温和略带颤音",
    },
    {
        "char_id": "stone_monkey",
        "name_zh": "石猴 / 美猴王",
        "role": "西游记主角",
        "age": 0,
        "canonical_image_url": "/samples/xiyou01_immortal_stone.jpg",
        "signature_marks": [
            "★ 金色毛发，瞳孔火焰金光",
            "★ 头戴紫金冠（封王后），手持如意金箍棒",
            "腰间虎皮裙，足蹬藕丝步云履",
        ],
        "voice": "顽皮少年音转洪亮中音",
    },
]

_LIBRARY_SCENES = [
    {
        "id": "lanruosi",
        "category": "古风寺庙",
        "name_zh": "兰若寺",
        "description": "破败古寺，夜雨初停，月光透瓦，蛛网密布",
        "keywords": ["夜晚", "兰若寺", "古寺", "月光", "白杨树", "破败"],
        "preview_cover_url": "/samples/nie01_lanruosi.jpg",
    },
    {
        "id": "baiyangshu",
        "category": "野外",
        "name_zh": "兰若白杨树",
        "description": "兰若寺旁千年白杨树，盘根错节，黑藤缠绕",
        "keywords": ["白杨树", "黑藤", "夜风", "枯枝", "鬼气"],
    },
    {
        "id": "ningjia",
        "category": "古风宅院",
        "name_zh": "宁家厢房",
        "description": "宁采臣家中厢房，木格窗，红木桌椅，烛火摇曳",
        "keywords": ["木格窗", "红木桌", "烛火", "床帐", "字画"],
    },
    {
        "id": "xitang",
        "category": "古风内堂",
        "name_zh": "宁家喜堂",
        "description": "ep08 鬼婚现场：红绸 / 龙凤烛 / 喜帖满堂",
        "keywords": ["红绸", "龙凤烛", "喜字", "红盖头", "拜堂"],
    },
    {
        "id": "yeshi",
        "category": "市井",
        "name_zh": "夜市灯影",
        "description": "古镇夜市，灯笼连绵，摊贩叫卖，行人如织",
        "keywords": ["灯笼", "夜市", "摊贩", "茶楼", "石板路"],
    },
    {
        "id": "huaguoshan",
        "category": "野外",
        "name_zh": "花果山",
        "description": "西游记开篇：花果山仙石，万年生灵气，蹦出石猴",
        "keywords": ["花果山", "仙石", "瀑布", "水帘洞", "猴群"],
        "preview_cover_url": "/samples/xiyou01_immortal_stone.jpg",
    },
]

_LIBRARY_EXPRESSIONS = [
    {"key": "shy", "name_zh": "羞涩低眉", "description": "低头微笑 + 眼神回避，适合女主初见 / 喜堂"},
    {"key": "shocked", "name_zh": "惊愕瞠目", "description": "瞳孔放大 + 嘴微张 + 眉毛上挑，剧情转折用"},
    {"key": "smile_warm", "name_zh": "温暖微笑", "description": "嘴角自然上扬 + 眼角微弯，人化后小倩常用"},
    {"key": "cry_silent", "name_zh": "默泪含情", "description": "眼眶湿润 + 一行清泪，不抽噎，悲情戏首选"},
    {"key": "fierce", "name_zh": "凌厉怒视", "description": "眉峰上挑 + 双目如电 + 唇线绷紧，侠客出剑前"},
    {"key": "afraid", "name_zh": "惊恐畏缩", "description": "眼神躲闪 + 嘴角颤抖 + 双肩收紧，被反派威胁"},
    {"key": "smile_eerie", "name_zh": "诡魅冷笑", "description": "嘴角斜上 + 眼神空洞 + 唇色偏冷，鬼魅期专用"},
    {"key": "determined", "name_zh": "坚毅决意", "description": "眉眼平直 + 嘴唇微抿 + 下颌微抬，关键抉择时"},
]

_LIBRARY_ACTIONS = [
    {"key": "walk_slow", "name_zh": "缓步行走", "description": "节奏放缓 4 步/秒，适合月夜出场 / 殿前踱步"},
    {"key": "kneel", "name_zh": "跪倒在地", "description": "双膝跪地 + 上身前倾，求情 / 告罪 / 拜堂"},
    {"key": "raise_sword", "name_zh": "拔剑出鞘", "description": "右手按剑柄 + 左手扶剑鞘 + 身体微沉，侠客准备战斗"},
    {"key": "hug", "name_zh": "紧拥入怀", "description": "双臂环抱 + 头侧靠肩，重逢 / 临别催泪戏"},
    {"key": "scroll_read", "name_zh": "执卷诵读", "description": "右手持卷 + 左手扶页 + 唇微动，书生标配"},
    {"key": "summon_vine", "name_zh": "黑藤召唤", "description": "右手画符 + 黑色藤蔓自地涌出，婆婆姥姥专属"},
    {"key": "bow_wedding", "name_zh": "拜堂三鞠", "description": "并肩三拜：天 / 地 / 高堂，喜堂场景固定动作"},
    {"key": "leap_cloud", "name_zh": "腾云驾雾", "description": "右脚踏云 + 衣袂飞扬，仙侠 / 西游御风戏"},
]

_LIBRARY_WARDROBE = [
    {"key": "ru_qun_white", "name_zh": "白色襦裙 + 浅粉缎带", "description": "小倩鬼魅期标配，外披薄纱披帛飘逸"},
    {"key": "ru_qun_pink", "name_zh": "浅粉襦裙 + 朱红腰带", "description": "小倩人化期，更明亮鲜活"},
    {"key": "xia_pei_red", "name_zh": "朱红霞帔 + 凤纹绣样", "description": "ep08-09 喜服，含红盖头"},
    {"key": "scholar_robe", "name_zh": "青衣襦袍 + 玉佩腰带", "description": "宁采臣赴试书生标准装束"},
    {"key": "daoist_red", "name_zh": "赤红道袍 + 朱砂符箓", "description": "燕赤霞侠客装束 + 长剑骨戒"},
    {"key": "tree_demon_grey", "name_zh": "灰色破衫 + 树皮披肩", "description": "婆婆姥姥树妖形态服饰"},
    {"key": "monkey_armor", "name_zh": "虎皮裙 + 紫金冠", "description": "美猴王封王后标配 + 藕丝步云履"},
]

# ---- 测试账号种子数据（无状态，按 user_id+slot 派生固定 job_id） ----
TEST_SEED_EMAILS = {"test1@139.com", "test2@139.com"}

# 每个测试账号注入 3 个完成态示例任务，便于全链路演示登录后即可看到作品
SEED_JOB_TEMPLATES = [
    {
        "title": "聊斋·兰若惊鸿",
        "novel_excerpt": "兰若寺夜雨初停，宁采臣独宿西厢。月光透窗，忽见一抹白影掠过回廊……",
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/nie01_lanruosi.mp4",
        "cover_url": "/samples/nie01_lanruosi.jpg",
    },
    {
        "title": "聊斋·小倩出场",
        "novel_excerpt": "月白冷青夜，朱砂痣定格在女鬼眉心。她回眸一笑，宁采臣心神俱失……",
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/nie02_appears.mp4",
        "cover_url": "/samples/nie02_appears.jpg",
    },
    {
        "title": "西游·石猴出世",
        "novel_excerpt": "花果山顶有一仙石，受日月精华，一日迸裂，化作一只石猴，目运两道金光，射冲斗府……",
        "genre": "xuanhuan",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/xiyou01_immortal_stone.mp4",
        "cover_url": "/samples/xiyou01_immortal_stone.jpg",
    },
]


def _seed_job_id(user_id: int, slot: int) -> int:
    """Stable deterministic job_id for a seeded test job (固定 ≤ 1_700_000_000 即可与时间戳 job_id 区分)。"""
    return 1_000_000 + user_id % 100_000 * 10 + slot  # 7~9 位数字，远离 1.7e9 时间戳区段


def _is_seed_email(email: str) -> bool:
    return email.lower().strip() in TEST_SEED_EMAILS


def _seed_jobs_for(uid: int, email: str) -> list[dict]:
    """Return the 3 pre-filled jobs for test1/test2 — all in 'succeeded' state with sample video."""
    if not _is_seed_email(email):
        return []
    out = []
    base_ts = 1_795_000_000  # 固定基准时间戳 (2026-12 左右)，让 created_at 看起来稳定
    for slot, tpl in enumerate(SEED_JOB_TEMPLATES):
        jid = _seed_job_id(uid, slot)
        created_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_ts - 86400 * (3 - slot)))
        out.append({
            "id": jid,
            "title": tpl["title"],
            "status": "succeeded",
            "progress": 100,
            "cost_cents": 0,
            "episodes": 1,
            "novel_excerpt": tpl["novel_excerpt"],
            "style": tpl["style"],
            "genre": tpl["genre"],
            "mode": "excerpt",
            "theme": None,
            "language": "Chinese",
            "result_url": tpl["video_url"],
            "cover_url": tpl["cover_url"],
            "error": None,
            "quality_score": 96 + (slot % 2),
            "quality_breakdown": {
                "tech": 38, "visual": 28, "narrative": 18, "genre": 9,
                "arcface": 9, "clip_align": 9, "aesthetic": 9, "hsv_color": 9, "motion": 9,
            },
            "quality_retries": 0,
            "current_step": 6,
            "step_artifacts": None,
            "pipeline_version": "v6-mock",
            "scores_7d": {
                "structure": 9.2, "style": 9.5, "detail": 9.0, "clarity": 9.3,
                "color": 9.1, "no_deform": 8.8, "intent": 9.4,
            },
            "human_approved": True,
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "fps": 24,
            "duration_per_episode_s": 80,
            "custom_style_id": None,
            "ui_mode": "wizard",
            "parent_id": None,
            "org_id": None,
            "confirm_required_at_steps": None,
            "created_at": created_iso,
            "updated_at": created_iso,
        })
    return out


def _seed_job_by_id(jid: int, uid: int, email: str) -> dict | None:
    """Resolve a single seed job by its derived id (or return None if not a seed slot)."""
    if not _is_seed_email(email):
        return None
    for slot in range(len(SEED_JOB_TEMPLATES)):
        if _seed_job_id(uid, slot) == jid:
            jobs = _seed_jobs_for(uid, email)
            if slot < len(jobs):
                return jobs[slot]
    return None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _init_db() -> None:
    conn = sqlite3.connect(_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS jobs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT, "
        "status TEXT DEFAULT 'queued', progress INTEGER DEFAULT 0, cost_cents INTEGER DEFAULT 0, "
        "episodes INTEGER DEFAULT 1, novel_excerpt TEXT, style TEXT, genre TEXT DEFAULT 'ancient', "
        "mode TEXT DEFAULT 'excerpt', theme TEXT, language TEXT DEFAULT 'Chinese', "
        "result_url TEXT, cover_url TEXT, error TEXT, quality_score INTEGER, "
        "quality_breakdown TEXT, quality_retries INTEGER DEFAULT 0, current_step INTEGER DEFAULT 0, "
        "step_artifacts TEXT, pipeline_version TEXT DEFAULT 'v6-mock', scores_7d TEXT, "
        "human_approved INTEGER DEFAULT 0, aspect_ratio TEXT DEFAULT '9:16', resolution TEXT DEFAULT '1080p', "
        "fps INTEGER DEFAULT 24, duration_per_episode_s INTEGER DEFAULT 80, custom_style_id TEXT, "
        "ui_mode TEXT DEFAULT 'wizard', created_at REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS job_logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, "
        "level TEXT, message TEXT, ts REAL NOT NULL)"
    )
    conn.commit()
    conn.close()


def _response(status: int, body: dict | list, *, extra_headers: dict | None = None) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status,
        "headers": headers,
        "isBase64Encoded": False,
        "body": json.dumps(body, ensure_ascii=False),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") and raw:
        raw = base64.b64decode(raw).decode("utf-8", errors="replace")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _path(event: dict) -> str:
    path = (event.get("path") or event.get("Path") or "").rstrip("/") or "/"
    if path.startswith("/api"):
        path = path[4:] or "/"
    return path


def _method(event: dict) -> str:
    return (event.get("httpMethod") or event.get("HTTPMethod") or "GET").upper()


def _headers(event: dict) -> dict[str, str]:
    h = event.get("headers") or event.get("Headers") or {}
    return {str(k).lower(): str(v) for k, v in h.items()}


def _token(user_id: int, email: str, *, credits_cents: int = SIGNUP_BONUS_CENTS,
           tier: str = "free", pwd_hash: str = "") -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "credits": credits_cents,
        "tier": tier,
        "pwd": pwd_hash,
        "exp": int(time.time()) + 86400 * 30,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def _decode_token(auth: str) -> dict | None:
    if not auth.startswith("Bearer "):
        return None
    raw = auth[7:].strip()
    pad = "=" * (-len(raw) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + pad))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def _require_user(hdrs: dict[str, str]) -> tuple | dict[str, Any]:
    payload = _decode_token(hdrs.get("authorization", ""))
    if not payload:
        return _response(401, {"detail": "Not authenticated"})
    return (
        int(payload["sub"]),
        str(payload["email"]),
        int(payload.get("credits", SIGNUP_BONUS_CENTS)),
        str(payload.get("tier", "free")),
    )


def _user_out(row: tuple) -> dict:
    return {
        "id": row[0],
        "email": row[1],
        "credits_cents": row[2],
        "tier": row[3] or "free",
        "created_at": _now_iso(),
    }


def _sample_bundles() -> list[tuple[str, str]]:
    if _CATALOG.is_file():
        data = json.loads(_CATALOG.read_text(encoding="utf-8"))
        out = []
        for s in data.get("samples", []):
            out.append((s.get("video_url", ""), s.get("cover_url", "")))
        if out:
            return out
    return [
        ("/samples/nie01_lanruosi.mp4", "/samples/nie01_lanruosi.jpg"),
        ("/samples/nie02_appears.mp4", "/samples/nie02_appears.jpg"),
    ]


def _synth_job_from_id(job_id: int, user_id: int) -> dict | None:
    """Synthesize job state purely from time-encoded id (stateless across instances).

    job_id 编码：bit 0..30 = unix_seconds since epoch when created。bit 31 reserved.
    """
    created = int(job_id)
    if created < 1_700_000_000 or created > 2_000_000_000:
        return None  # not a time-encoded id
    elapsed = time.time() - created
    if elapsed < 0:
        return None
    if elapsed < MOCK_RENDER_SECONDS:
        status = "queued" if elapsed < 2 else "running"
        progress = max(0, min(99, int(elapsed / MOCK_RENDER_SECONDS * 100)))
        current_step = max(1, min(6, progress // 17 + 1))
        result_url = None
        cover_url = None
        quality_score = None
        scores_7d = None
        breakdown = None
    else:
        bundles = _sample_bundles()
        video, cover = bundles[created % len(bundles)]
        status = "succeeded"
        progress = 100
        current_step = 6
        result_url = video
        cover_url = cover
        quality_score = 96
        breakdown = {"tech": 38, "visual": 28, "narrative": 18, "genre": 9,
                     "arcface": 9, "clip_align": 9, "aesthetic": 9, "hsv_color": 9, "motion": 9}
        scores_7d = {"structure": 9.2, "style": 9.5, "detail": 9.0, "clarity": 9.3,
                     "color": 9.1, "no_deform": 8.8, "intent": 9.4}
    return {
        "id": job_id,
        "title": "未命名漫剧",
        "status": status,
        "progress": progress,
        "cost_cents": 0,
        "episodes": 1,
        "novel_excerpt": "",
        "style": "ancient_3d_guoman",
        "genre": "ancient",
        "mode": "excerpt",
        "theme": None,
        "language": "Chinese",
        "result_url": result_url,
        "cover_url": cover_url,
        "error": None,
        "quality_score": quality_score,
        "quality_breakdown": breakdown,
        "quality_retries": 0,
        "current_step": current_step,
        "step_artifacts": None,
        "pipeline_version": "v6-mock",
        "scores_7d": scores_7d,
        "human_approved": False,
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "fps": 24,
        "duration_per_episode_s": 80,
        "custom_style_id": None,
        "ui_mode": "wizard",
        "parent_id": None,
        "org_id": None,
        "confirm_required_at_steps": None,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created)),
        "updated_at": _now_iso(),
    }


def _official_samples() -> list[dict]:
    if _CATALOG.is_file():
        data = json.loads(_CATALOG.read_text(encoding="utf-8"))
        return [{k: v for k, v in s.items() if k != "slug"} for s in data.get("samples", [])]
    return []


def _add_log(conn: sqlite3.Connection, job_id: int, level: str, message: str) -> None:
    conn.execute(
        "INSERT INTO job_logs(job_id, level, message, ts) VALUES (?, ?, ?, ?)",
        (job_id, level, message, time.time()),
    )


def _free_jobs_today(conn: sqlite3.Connection, user_id: int) -> int:
    start = time.time() - (time.time() % 86400)
    row = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE user_id=? AND created_at>=? AND status!='cancelled'",
        (user_id, start),
    ).fetchone()
    return int(row[0]) if row else 0


def _job_row_to_dict(row: sqlite3.Row, *, tick: bool = False) -> dict:
    data = dict(row)
    if tick and data["status"] in ("queued", "running"):
        elapsed = time.time() - float(data["created_at"])
        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        if elapsed >= MOCK_RENDER_SECONDS:
            bundles = _sample_bundles()
            video, cover = bundles[data["id"] % len(bundles)]
            breakdown = {
                "tech": 38, "visual": 28, "narrative": 18, "genre": 9,
                "arcface": 9, "clip_align": 9, "aesthetic": 9, "hsv_color": 9, "motion": 9,
            }
            scores_7d = {
                "structure": 9.2, "style": 9.5, "detail": 9.0, "clarity": 9.3,
                "color": 9.1, "no_deform": 8.8, "intent": 9.4,
            }
            conn.execute(
                "UPDATE jobs SET status='succeeded', progress=100, current_step=6, "
                "result_url=?, cover_url=?, quality_score=96, quality_breakdown=?, "
                "scores_7d=?, updated_at=? WHERE id=? AND status IN ('queued','running')",
                (
                    video, cover, json.dumps(breakdown), json.dumps(scores_7d),
                    time.time(), data["id"],
                ),
            )
            if conn.total_changes:
                _add_log(conn, data["id"], "INFO", "✅ 任务完成，质量 96/100 已达标，可下载 MP4")
            conn.commit()
        elif elapsed >= 3:
            progress = min(99, int(elapsed / MOCK_RENDER_SECONDS * 100))
            conn.execute(
                "UPDATE jobs SET status='running', progress=?, current_step=?, updated_at=? "
                "WHERE id=? AND status IN ('queued','running')",
                (progress, min(6, progress // 17 + 1), time.time(), data["id"]),
            )
            conn.commit()
        conn.close()
        conn2 = sqlite3.connect(_DB)
        conn2.row_factory = sqlite3.Row
        refreshed = conn2.execute("SELECT * FROM jobs WHERE id=?", (data["id"],)).fetchone()
        conn2.close()
        if refreshed:
            data = dict(refreshed)

    qb = data.get("quality_breakdown")
    s7 = data.get("scores_7d")
    try:
        qb_obj = json.loads(qb) if qb else None
    except Exception:
        qb_obj = None
    try:
        s7_obj = json.loads(s7) if s7 else None
    except Exception:
        s7_obj = None

    created = float(data["created_at"])
    updated = float(data["updated_at"])
    return {
        "id": data["id"],
        "title": data["title"],
        "status": data["status"],
        "progress": data["progress"],
        "cost_cents": data["cost_cents"],
        "episodes": data["episodes"],
        "novel_excerpt": data["novel_excerpt"] or "",
        "style": data["style"],
        "genre": data["genre"] or "ancient",
        "mode": data["mode"] or "excerpt",
        "theme": data["theme"],
        "language": data["language"] or "Chinese",
        "result_url": data["result_url"],
        "cover_url": data["cover_url"],
        "error": data["error"],
        "quality_score": data["quality_score"],
        "quality_breakdown": qb_obj,
        "quality_retries": data["quality_retries"] or 0,
        "current_step": data["current_step"] or 0,
        "step_artifacts": None,
        "pipeline_version": data["pipeline_version"] or "v6-mock",
        "scores_7d": s7_obj,
        "human_approved": bool(data["human_approved"]),
        "aspect_ratio": data["aspect_ratio"] or "9:16",
        "resolution": data["resolution"] or "1080p",
        "fps": data["fps"] or 24,
        "duration_per_episode_s": data["duration_per_episode_s"] or 80,
        "custom_style_id": data["custom_style_id"],
        "ui_mode": data["ui_mode"] or "wizard",
        "parent_id": None,
        "org_id": None,
        "confirm_required_at_steps": None,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created)),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(updated)),
    }


def _route(event: dict) -> dict[str, Any]:
    path = _path(event)
    method = _method(event)
    body = _parse_body(event)
    hdrs = _headers(event)

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
                "Access-Control-Allow-Headers": "Authorization,Content-Type",
            },
            "body": "",
        }

    _init_db()

    if path.endswith("/health") or path.endswith("/healthz"):
        return _response(200, {"status": "ok", "mock_worker": True, "mock_billing": True})

    if re.match(r"^/genres/?$", path) and method == "GET":
        return _response(200, _GENRES)

    m = re.match(r"^/genres/([^/]+)$", path)
    if m and method == "GET":
        gid = m.group(1)
        for g in _GENRES:
            if g["id"] == gid:
                return _response(200, g)
        return _response(404, {"detail": "genre 不存在"})

    if path.endswith("/gallery") and method == "GET":
        return _response(200, _official_samples())

    if path.endswith("/auth/guest") and method == "POST":
        raw_id = (body.get("guest_id") or "").strip().lower()
        if raw_id and re.match(r"^[a-z0-9]{8,32}$", raw_id):
            guest_id = raw_id
        else:
            guest_id = secrets.token_hex(8)
        email = f"guest-{guest_id}@xyq.local"
        uid = _user_id(email)
        tok = _token(uid, email, credits_cents=SIGNUP_BONUS_CENTS, tier="free", pwd_hash="")
        return _response(
            200,
            {
                "token": tok,
                "user": _user_out((uid, email, SIGNUP_BONUS_CENTS, "free")),
                "guest_id": guest_id,
                "is_guest": True,
            },
        )

    if path.endswith("/auth/signup") and method == "POST":
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        if not email or not password:
            return _response(400, {"detail": "email/password required"})
        if "@" not in email or "." not in email:
            return _response(400, {"detail": "邮箱格式不正确"})
        if len(password) < 6:
            return _response(400, {"detail": "密码至少 6 位"})
        uid = _user_id(email)
        pwd = _pwd_hash(email, password)
        tok = _token(uid, email, credits_cents=SIGNUP_BONUS_CENTS, tier="free", pwd_hash=pwd)
        return _response(
            201,
            {
                "token": tok,
                "user": _user_out((uid, email, SIGNUP_BONUS_CENTS, "free")),
            },
        )

    if path.endswith("/auth/login") and method == "POST":
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        if not email or len(password) < 6:
            return _response(401, {"detail": "邮箱或密码不正确"})
        uid = _user_id(email)
        pwd = _pwd_hash(email, password)
        tok = _token(uid, email, credits_cents=SIGNUP_BONUS_CENTS, tier="free", pwd_hash=pwd)
        return _response(
            200,
            {
                "token": tok,
                "user": _user_out((uid, email, SIGNUP_BONUS_CENTS, "free")),
            },
        )

    if path.endswith("/auth/me") and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        return _response(200, _user_out(auth))

    if path.endswith("/jobs/quota") and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        uid, _, credits, tier = auth[0], auth[1], auth[2], auth[3]
        conn = sqlite3.connect(_DB)
        used = _free_jobs_today(conn, uid) if tier == "free" else 0
        conn.close()
        cost = 0 if tier in ("free", "admin") else int(round(EPISODE_BASE_COST_CENTS * PROFIT_MULTIPLIER))
        return _response(
            200,
            {
                "tier": tier or "free",
                "credits_cents": credits,
                "free_daily_limit": FREE_DAILY_QUOTA,
                "free_used_today": used,
                "free_remaining_today": max(0, FREE_DAILY_QUOTA - used) if tier == "free" else None,
                "cost_per_episode_cents": cost,
                "episode_base_cost_cents": EPISODE_BASE_COST_CENTS,
                "profit_multiplier": PROFIT_MULTIPLIER,
            },
        )

    if re.match(r"^/jobs/?$", path) and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        uid, email = auth[0], auth[1]

        real_views: list[dict] = []
        if real_jobs is not None and real_jobs.is_real_mode_enabled():
            try:
                states = real_jobs.list_user_jobs(uid)
                real_views = [real_jobs.to_job_view(s) for s in states]
            except Exception as e:  # noqa: BLE001
                _log.warning("real_jobs.list_user_jobs failed: %s", e)

        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 100",
            (uid,),
        ).fetchall()
        conn.close()
        live_jobs = [_job_row_to_dict(r, tick=True) for r in rows]
        seed_jobs = _seed_jobs_for(uid, email)
        seen = {j["id"] for j in real_views}
        for j in live_jobs:
            if j["id"] not in seen:
                real_views.append(j)
                seen.add(j["id"])
        for j in seed_jobs:
            if j["id"] not in seen:
                real_views.append(j)
                seen.add(j["id"])
        real_views.sort(key=lambda j: j["id"], reverse=True)
        return _response(200, real_views)

    if re.match(r"^/jobs/?$", path) and method == "POST":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        uid, email, credits, tier = auth[0], auth[1], auth[2], auth[3]
        episodes = int(body.get("episodes") or 1)
        mode = body.get("mode") or "excerpt"
        if tier == "free" and episodes > 1:
            return _response(403, {"detail": "免费用户单次只能生成 1 集。十集套装请升级为付费用户。"})
        cost = 0 if tier in ("free", "admin") else int(round(EPISODE_BASE_COST_CENTS * episodes * PROFIT_MULTIPLIER))
        if cost > credits:
            return _response(402, {"detail": f"余额不足：需要 ¥{cost/100:.2f}，当前 ¥{credits/100:.2f}"})
        if mode == "theme":
            theme = (body.get("theme") or "").strip()
            if len(theme) < 4:
                return _response(400, {"detail": "theme 模式下需提供 ≥ 4 字的主题"})
            novel_text = body.get("novel_excerpt") or f"theme:{theme}"
        else:
            excerpt = (body.get("novel_excerpt") or "").strip()
            if len(excerpt) < 50:
                return _response(400, {"detail": "小说片段至少 50 字"})
            novel_text = excerpt

        if real_jobs is not None and real_jobs.is_real_mode_enabled():
            try:
                state = real_jobs.create_job(
                    user_id=uid, user_email=email,
                    novel_excerpt=novel_text,
                    title=body.get("title") or "未命名漫剧",
                    style=body.get("style") or "ancient_3d_guoman",
                    genre=body.get("genre") or "ancient",
                    language=body.get("language") or "Chinese",
                    episodes=episodes,
                    aspect_ratio=body.get("aspect_ratio") or "9:16",
                    mode=mode,
                    theme=body.get("theme"),
                    cost_cents=cost,
                )
                view = real_jobs.to_job_view(state)
                if state.get("status") == "failed":
                    return _response(502, {"detail": state.get("error") or "submit failed",
                                           "job": view})
                return _response(201, view)
            except Exception as e:  # noqa: BLE001
                _log.exception("real_jobs.create_job failed; falling back to mock")
                return _response(502, {"detail": f"火山 Agent 提交失败：{e}"})

        now = time.time()
        job_id = int(now)  # time-encoded id → stateless lookup
        # Also persist in /tmp for the (lucky) hits to the same instance — lists, logs.
        try:
            conn = sqlite3.connect(_DB)
            conn.execute(
                "INSERT OR REPLACE INTO jobs(id, user_id, title, novel_excerpt, style, episodes, cost_cents, genre, mode, "
                "theme, language, status, progress, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?)",
                (
                    job_id, uid,
                    body.get("title") or "未命名漫剧",
                    novel_text,
                    body.get("style") or "ancient_3d_guoman",
                    episodes, cost,
                    body.get("genre") or "ancient",
                    mode, body.get("theme"),
                    body.get("language") or "Chinese",
                    now, now,
                ),
            )
            _add_log(conn, job_id, "INFO", f"[worker] pull job #{job_id} '{body.get('title') or '未命名漫剧'}' ({episodes} 集)")
            _add_log(conn, job_id, "INFO", "[Step1] [shell1_script] 剧本拆解与分镜规划")
            conn.commit()
            conn.close()
        except Exception:
            pass
        synth = _synth_job_from_id(job_id, uid) or {}
        synth["title"] = body.get("title") or "未命名漫剧"
        synth["novel_excerpt"] = novel_text
        synth["style"] = body.get("style") or "ancient_3d_guoman"
        synth["episodes"] = episodes
        synth["cost_cents"] = cost
        synth["genre"] = body.get("genre") or "ancient"
        synth["mode"] = mode
        synth["theme"] = body.get("theme")
        synth["language"] = body.get("language") or "Chinese"
        return _response(201, synth)

    m = re.match(r"^/jobs/(\d+)/logs$", path)
    if m and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        job_id = int(m.group(1))

        if real_jobs is not None and real_jobs.is_real_mode_enabled():
            try:
                state = real_jobs.load_state(auth[0], job_id)
                if state:
                    return _response(200, real_jobs.to_log_view(state))
            except Exception as e:  # noqa: BLE001
                _log.warning("real_jobs.to_log_view(%s) failed: %s", job_id, e)

        # Try DB first; fall back to synthetic timeline derived from job_id
        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT level, message, ts FROM job_logs WHERE job_id=? ORDER BY id",
            (job_id,),
        ).fetchall()
        conn.close()
        if rows:
            return _response(
                200,
                [
                    {
                        "level": lg["level"],
                        "message": lg["message"],
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(lg["ts"]))),
                    }
                    for lg in rows
                ],
            )
        # 种子任务（test1/test2）：合成完整成功 timeline
        seed = _seed_job_by_id(job_id, auth[0], auth[1])
        if seed:
            base_ts = int(time.mktime(time.strptime(seed["created_at"], "%Y-%m-%dT%H:%M:%SZ")))
            timeline = [
                (base_ts, "INFO", f"[worker] pull job #{job_id} '{seed['title']}'"),
                (base_ts + 1, "INFO", "[Step1] [shell1_script] 剧本拆解与分镜规划"),
                (base_ts + 5, "INFO", "[Step2] [shell2_assets] 角色与场景资产生成"),
                (base_ts + 10, "INFO", "[Step3] [shell3_prompts] 分镜提示词序列化"),
                (base_ts + 14, "INFO", "[Step4] [shell4_skylark] 抽卡渲染视频帧"),
                (base_ts + 19, "INFO", "[Step5] [shell5_post] 初剪 + LUFS 归一化"),
                (base_ts + 23, "INFO", "[Step6] [shell6_qa_final] 7 维评分 + 一致性校验"),
                (base_ts + 24, "INFO", f"📊 100-Pt Rubric 总分 = {seed['quality_score']}/100"),
                (base_ts + 25, "INFO", "✅ 任务完成，质量已达标，可下载 MP4"),
            ]
            return _response(
                200,
                [
                    {
                        "level": lvl,
                        "message": msg,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                    }
                    for ts, lvl, msg in timeline
                ],
            )
        synth = _synth_job_from_id(job_id, auth[0])
        if not synth:
            return _response(404, {"detail": "任务不存在"})
        created = int(job_id)
        timeline = [
            (created, "INFO", f"[worker] pull job #{job_id}"),
            (created + 1, "INFO", "[Step1] [shell1_script] 剧本拆解与分镜规划"),
            (created + 5, "INFO", "[Step2] [shell2_assets] 角色与场景资产生成"),
            (created + 10, "INFO", "[Step3] [shell3_prompts] 分镜提示词序列化"),
            (created + 14, "INFO", "[Step4] [shell4_skylark] 抽卡渲染视频帧"),
            (created + 19, "INFO", "[Step5] [shell5_post] 初剪 + LUFS 归一化"),
            (created + 23, "INFO", "[Step6] [shell6_qa_final] 7 维评分 + 一致性校验"),
            (created + 25, "INFO", "📊 100-Pt Rubric 总分 = 96/100"),
            (created + 25, "INFO", "✅ 任务完成，质量 96/100 已达标，可下载 MP4"),
        ]
        now = time.time()
        return _response(
            200,
            [
                {
                    "level": lvl,
                    "message": msg,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                }
                for ts, lvl, msg in timeline if ts <= now
            ],
        )

    m = re.match(r"^/jobs/(\d+)/cancel$", path)
    if m and method == "POST":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        job_id = int(m.group(1))
        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
        if not row:
            conn.close()
            return _response(404, {"detail": "任务不存在"})
        if row["status"] in ("succeeded", "failed", "cancelled"):
            conn.close()
            return _response(400, {"detail": f"任务已是 {row['status']}，不可取消"})
        refund = int(round(row["cost_cents"] * max(0.0, 1.0 - row["progress"] / 100.0)))
        if refund > 0:
            conn.execute("UPDATE users SET credits_cents=credits_cents+? WHERE id=?", (refund, auth[0]))
            _add_log(conn, job_id, "INFO", f"取消，退回 ¥{refund/100:.2f}")
        conn.execute(
            "UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?",
            (time.time(), job_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        return _response(200, _job_row_to_dict(row))

    m = re.match(r"^/jobs/(\d+)/approve$", path)
    if m and method == "POST":
        return _job_mutate(hdrs, int(m.group(1)), approve=True)

    m = re.match(r"^/jobs/(\d+)/reroll$", path)
    if m and method == "POST":
        return _job_mutate(hdrs, int(m.group(1)), reroll=True)

    m = re.match(r"^/jobs/(\d+)/versions$", path)
    if m and method == "GET":
        return _job_versions(hdrs, int(m.group(1)))

    m = re.match(r"^/jobs/(\d+)/shots$", path)
    if m and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        return _response(200, [])

    m = re.match(r"^/jobs/(\d+)/marketing$", path)
    if m and method == "GET":
        return _job_marketing(hdrs, int(m.group(1)))

    m = re.match(r"^/jobs/(\d+)/interaction-graph$", path)
    if m and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        return _response(200, {"nodes": [], "edges": []})

    m = re.match(r"^/jobs/(\d+)/versions/rollback$", path)
    if m and method == "POST":
        return _job_mutate(hdrs, int(m.group(1)), approve=False, reroll=False)

    m = re.match(r"^/jobs/(\d+)/continue$", path)
    if m and method == "POST":
        return _job_clone(hdrs, int(m.group(1)), body, kind="continue")

    m = re.match(r"^/jobs/(\d+)/restyle$", path)
    if m and method == "POST":
        return _job_clone(hdrs, int(m.group(1)), body, kind="restyle")

    m = re.match(r"^/jobs/(\d+)/translate$", path)
    if m and method == "POST":
        return _job_clone(hdrs, int(m.group(1)), body, kind="translate")

    m = re.match(r"^/jobs/(\d+)/shots/(\d+)(/[^/]+)?$", path)
    if m:
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        return _response(404, {"detail": "镜头不存在（mock 模式）"})

    if re.match(r"^/jobs/(\d+)/export$", path) and method == "POST":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        job_id = int(re.match(r"^/jobs/(\d+)/export$", path).group(1))
        title = None
        result_url = ""
        cover_url = None

        if real_jobs is not None and real_jobs.is_real_mode_enabled():
            try:
                state = real_jobs.load_state(auth[0], job_id)
                if state and state.get("result_url"):
                    title = state.get("title")
                    result_url = state.get("result_url") or ""
                    cover_url = state.get("cover_url")
            except Exception as e:  # noqa: BLE001
                _log.warning("real_jobs export load_state failed: %s", e)

        if title is None:
            conn = sqlite3.connect(_DB)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
            conn.close()
            if row:
                title = row["title"]
                result_url = row["result_url"] or ""
                cover_url = row["cover_url"]
            else:
                seed = _seed_job_by_id(job_id, auth[0], auth[1])
                if seed:
                    title = seed["title"]
                    result_url = seed["result_url"] or ""
                    cover_url = seed["cover_url"]
        if title is None:
            return _response(404, {"detail": "任务不存在"})
        platforms = body.get("platforms") or ["douyin"]
        return _response(
            200,
            [
                {
                    "platform": p,
                    "url": result_url,
                    "cover_url": cover_url,
                    "caption": f"AI 漫剧 · {title}",
                    "hashtags": ["#AI漫剧", "#国漫", "#爆款短剧"],
                    "duration_s": 80,
                    "width": 1080,
                    "height": 1920,
                }
                for p in platforms
            ],
        )

    m = re.match(r"^/jobs/(\d+)$", path)
    if m and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        job_id = int(m.group(1))

        if real_jobs is not None and real_jobs.is_real_mode_enabled():
            try:
                state = real_jobs.load_state(auth[0], job_id)
                if state:
                    state = real_jobs.step(state)
                    return _response(200, real_jobs.to_job_view(state))
            except Exception as e:  # noqa: BLE001
                _log.warning("real_jobs step(%s) failed: %s", job_id, e)

        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
        conn.close()
        if row:
            return _response(200, _job_row_to_dict(row, tick=True))
        seed = _seed_job_by_id(job_id, auth[0], auth[1])
        if seed:
            return _response(200, seed)
        synth = _synth_job_from_id(job_id, auth[0])
        if synth:
            return _response(200, synth)
        return _response(404, {"detail": "任务不存在"})

    if path.endswith("/billing/checkout") and method == "POST":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        plan = body.get("plan") or "starter"
        if plan not in _PLANS:
            return _response(400, {"detail": "未知套餐"})
        return _response(200, {"url": "/billing/success?mock=1", "mocked": True})

    if path.endswith("/billing/topup") and method == "POST":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        amount = int(body.get("amount_cents") or 0)
        if amount <= 0:
            return _response(400, {"detail": "amount_cents 无效"})
        new_credits = auth[2] + amount
        return _response(200, _user_out((auth[0], auth[1], new_credits, "pro")))

    if path == "/library/characters" and method == "GET":
        return _response(200, _LIBRARY_CHARACTERS)
    if path == "/library/scenes" and method == "GET":
        cat = ""
        try:
            from urllib.parse import urlparse, parse_qs
            qs_raw = event.get("queryString") or event.get("queryStringParameters") or ""
            if isinstance(qs_raw, dict):
                cat = (qs_raw.get("category") or "").strip()
            elif isinstance(qs_raw, str) and qs_raw:
                qs = parse_qs(qs_raw.lstrip("?"))
                cat = (qs.get("category", [""])[0] or "").strip()
        except Exception:  # noqa: BLE001
            cat = ""
        if cat:
            return _response(200, [s for s in _LIBRARY_SCENES if s.get("category") == cat])
        return _response(200, _LIBRARY_SCENES)
    if path == "/library/expressions" and method == "GET":
        return _response(200, _LIBRARY_EXPRESSIONS)
    if path == "/library/actions" and method == "GET":
        return _response(200, _LIBRARY_ACTIONS)
    if path == "/library/wardrobe" and method == "GET":
        return _response(200, _LIBRARY_WARDROBE)
    m = re.match(r"^/library/characters/([^/]+)$", path)
    if m and method == "GET":
        cid = m.group(1)
        for c in _LIBRARY_CHARACTERS:
            if c["char_id"] == cid:
                return _response(200, c)
        return _response(404, {"detail": "character 不存在"})
    m = re.match(r"^/library/scenes/([^/]+)$", path)
    if m and method == "GET":
        sid = m.group(1)
        for s in _LIBRARY_SCENES:
            if s["id"] == sid:
                return _response(200, s)
        return _response(404, {"detail": "scene 不存在"})

    if re.match(r"^/batch/?$", path) and method == "GET":
        auth = _require_user(hdrs)
        if isinstance(auth, dict):
            return auth
        return _response(200, [])

    return _response(404, {"detail": f"Not Found: {method} {path}"})


def _job_mutate(hdrs: dict[str, str], job_id: int, *, approve: bool = False, reroll: bool = False) -> dict[str, Any]:
    auth = _require_user(hdrs)
    if isinstance(auth, dict):
        return auth
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
    if not row:
        conn.close()
        return _response(404, {"detail": "任务不存在"})
    if approve:
        conn.execute("UPDATE jobs SET human_approved=1, updated_at=? WHERE id=?", (time.time(), job_id))
        _add_log(conn, job_id, "INFO", "用户已人工确认放行")
    if reroll:
        conn.execute(
            "UPDATE jobs SET status='queued', progress=0, current_step=0, human_approved=0, error=NULL, updated_at=? WHERE id=?",
            (time.time(), job_id),
        )
        _add_log(conn, job_id, "INFO", "用户触发重绘 scope=full")
    conn.commit()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return _response(200, _job_row_to_dict(row))


def _job_versions(hdrs: dict[str, str], job_id: int) -> dict[str, Any]:
    auth = _require_user(hdrs)
    if isinstance(auth, dict):
        return auth

    if real_jobs is not None and real_jobs.is_real_mode_enabled():
        try:
            state = real_jobs.load_state(auth[0], job_id)
            if state and state.get("result_url"):
                return _response(200, [{
                    "id": 1, "version_no": 1,
                    "quality_score": 96,
                    "scores_7d": {"structure": 9.2, "style": 9.5, "detail": 9.0,
                                  "clarity": 9.3, "color": 9.1, "no_deform": 8.8,
                                  "intent": 9.4},
                    "result_url": state.get("result_url"),
                    "cover_url": state.get("cover_url"),
                    "notes": "初版（火山 Manju Agent 真实生成）",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                time.gmtime(int(state.get("updated_at_ts") or 0))),
                }])
            if state:
                return _response(200, [])
        except Exception as e:  # noqa: BLE001
            _log.warning("real_jobs versions load failed: %s", e)

    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
    conn.close()
    if row:
        if row["status"] != "succeeded":
            return _response(200, [])
        return _response(
            200,
            [{
                "id": 1,
                "version_no": 1,
                "quality_score": row["quality_score"],
                "scores_7d": json.loads(row["scores_7d"]) if row["scores_7d"] else None,
                "result_url": row["result_url"],
                "cover_url": row["cover_url"],
                "notes": "初版",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(row["updated_at"]))),
            }],
        )
    seed = _seed_job_by_id(job_id, auth[0], auth[1])
    if seed:
        return _response(
            200,
            [{
                "id": 1,
                "version_no": 1,
                "quality_score": seed["quality_score"],
                "scores_7d": seed["scores_7d"],
                "result_url": seed["result_url"],
                "cover_url": seed["cover_url"],
                "notes": "初版",
                "created_at": seed["created_at"],
            }],
        )
    return _response(404, {"detail": "任务不存在"})


def _job_marketing(hdrs: dict[str, str], job_id: int) -> dict[str, Any]:
    auth = _require_user(hdrs)
    if isinstance(auth, dict):
        return auth
    title = None
    genre = "ancient"
    episodes = 1
    language = "Chinese"

    if real_jobs is not None and real_jobs.is_real_mode_enabled():
        try:
            state = real_jobs.load_state(auth[0], job_id)
            if state:
                title = state.get("title")
                genre = state.get("genre") or "ancient"
                episodes = state.get("episodes_requested") or 1
                language = state.get("language") or "Chinese"
        except Exception as e:  # noqa: BLE001
            _log.warning("real_jobs marketing load failed: %s", e)

    if title is None:
        conn = sqlite3.connect(_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
        conn.close()
        if row:
            title = row["title"]
            genre = row["genre"] or "ancient"
            episodes = row["episodes"] or 1
            language = row["language"] or "Chinese"
        else:
            seed = _seed_job_by_id(job_id, auth[0], auth[1])
            if seed:
                title = seed["title"]
                genre = seed["genre"]
                episodes = seed["episodes"]
                language = seed["language"]
    if title is None:
        return _response(404, {"detail": "任务不存在"})
    return _response(
        200,
        {
            "title": title,
            "summary": f"{genre} 题材 AI 漫剧 · {episodes} 集 · 全网首发",
            "hook_copy": f"看到第 3 秒你就停不下来 — 《{title}》",
            "hashtags": [f"#{genre}", "#AI漫剧", "#爆款短剧", "#国漫"],
            "language": language,
        },
    )


def _job_clone(hdrs: dict[str, str], job_id: int, body: dict, *, kind: str) -> dict[str, Any]:
    auth = _require_user(hdrs)
    if isinstance(auth, dict):
        return auth
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, auth[0])).fetchone()
    if not row:
        conn.close()
        return _response(404, {"detail": "任务不存在"})
    now = time.time()
    if kind == "continue":
        extra = int(body.get("extra_episodes") or 1)
        new_title = f"{row['title']} · 续集"
        new_excerpt = (body.get("direction") or "续写") + "\n\n" + (row["novel_excerpt"] or "")
        episodes = extra
    elif kind == "restyle":
        style_map = {
            "jpn_anime": "japanese_anime",
            "guoman": "ancient_3d_guoman",
            "realistic": "cinematic_realistic",
            "manhwa": "korean_manhwa",
        }
        new_style = style_map.get(body.get("target"), row["style"])
        conn.execute(
            "UPDATE jobs SET style=?, status='queued', progress=0, current_step=0, updated_at=? WHERE id=?",
            (new_style, now, job_id),
        )
        _add_log(conn, job_id, "INFO", f"风格迁移 → {body.get('target')}")
        conn.commit()
        refreshed = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        return _response(200, _job_row_to_dict(refreshed))
    else:  # translate
        lang = body.get("target_lang") or "English"
        conn.execute("UPDATE jobs SET language=?, updated_at=? WHERE id=?", (lang, now, job_id))
        _add_log(conn, job_id, "INFO", f"翻译目标语言 → {lang}")
        conn.commit()
        refreshed = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        return _response(200, _job_row_to_dict(refreshed))

    cur = conn.execute(
        "INSERT INTO jobs(user_id, title, novel_excerpt, style, episodes, cost_cents, genre, mode, "
        "theme, language, status, progress, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?, 'excerpt', ?, ?, 'queued', 0, ?, ?)",
        (
            auth[0], new_title, new_excerpt, row["style"], episodes,
            row["genre"], row["theme"], row["language"], now, now,
        ),
    )
    new_id = cur.lastrowid
    _add_log(conn, new_id, "INFO", f"由 #{job_id} 续写 +{episodes} 集")
    conn.commit()
    refreshed = conn.execute("SELECT * FROM jobs WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return _response(201, _job_row_to_dict(refreshed))


def main_handler(event: dict, context: Any) -> dict[str, Any]:
    try:
        return _route(event)
    except Exception as exc:  # pragma: no cover
        return _response(500, {"detail": str(exc)})


main = main_handler
