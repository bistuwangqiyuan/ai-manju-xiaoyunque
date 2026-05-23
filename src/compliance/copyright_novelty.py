"""LLM-based copyright novelty check (requirement doc §11.3 版权自动辨别).

Compares user-supplied text against a fingerprint library of known IPs
(movies, novels, anime). Returns a risk score 0-1 with the closest matches.

Two backends:
    - Anthropic Claude (preferred) — JSON-only response, low temperature
    - mock (deterministic) — uses string-overlap heuristics, no API needed
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


# Curated mini-fingerprint library. Each entry holds the IP name + a list of
# rare/independent signals (character names, locations, plot beats) that
# uniquely identify it.
_FINGERPRINT_LIBRARY: list[dict] = [
    {
        "ip": "倩女幽魂(徐克1987)",
        "signals": ["长舌姥姥", "树妖长舌", "宁采臣浴桶", "黑山老妖", "张国荣造型"],
    },
    {
        "ip": "哈利波特",
        "signals": ["霍格沃茨", "魁地奇", "伏地魔", "对角巷", "麻瓜", "马尔福", "魂器"],
    },
    {
        "ip": "三体",
        "signals": ["三体人", "智子", "黑暗森林", "面壁者", "罗辑", "叶文洁", "降维打击"],
    },
    {
        "ip": "庆余年",
        "signals": ["范闲", "范若若", "庆帝", "言冰云", "陈萍萍", "鉴查院", "靖王"],
    },
    {
        "ip": "魔道祖师",
        "signals": ["夷陵老祖", "魏无羡", "蓝忘机", "云深不知处", "鬼将军", "陈情笛", "温情温宁"],
    },
    {
        "ip": "天官赐福",
        "signals": ["谢怜", "花城", "三郎", "上天庭", "君吾", "鬼市", "白无相"],
    },
    {
        "ip": "海贼王",
        "signals": ["路飞", "草帽海贼团", "橡胶果实", "ONE PIECE", "凯多", "白胡子"],
    },
    {
        "ip": "鬼灭之刃",
        "signals": ["炭治郎", "祢豆子", "鬼杀队", "无限城", "上弦", "下弦"],
    },
    {
        "ip": "进击的巨人",
        "signals": ["艾伦", "三笠", "立体机动", "调查兵团", "玛利亚之墙", "始祖巨人"],
    },
    {
        "ip": "西游记原著",
        "signals": ["孙悟空", "唐三藏", "猪八戒", "沙和尚", "金箍棒", "如来佛祖", "牛魔王"],
    },
]


@dataclass
class NoveltyReport:
    risk_score: float
    similar_ips: list[dict] = field(default_factory=list)
    method: str = "mock"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "risk_score": round(self.risk_score, 3),
            "similar_ips": self.similar_ips,
            "method": self.method,
            "notes": self.notes,
        }


def novelty_check(text: str) -> dict:
    """Return a dict suitable for embedding in orchestrator artifacts."""
    if os.environ.get("FORCE_MOCK_NOVELTY") == "1" or not os.environ.get("ANTHROPIC_API_KEY"):
        return _heuristic(text).to_dict()
    try:
        return _via_anthropic(text).to_dict()
    except Exception as e:  # pragma: no cover
        _log.warning("anthropic novelty check failed: %s; falling back to heuristic", e)
        return _heuristic(text).to_dict()


def _heuristic(text: str) -> NoveltyReport:
    """Signal-overlap heuristic. Each match contributes risk; ≥ 3 unique
    signals of one IP → high risk (0.85+)."""
    norm = text.lower()
    hits: list[dict] = []
    max_score = 0.0
    for entry in _FINGERPRINT_LIBRARY:
        matched: list[str] = []
        for signal in entry["signals"]:
            if signal.lower() in norm:
                matched.append(signal)
        if matched:
            score = min(1.0, len(matched) / 3.0)
            hits.append({"ip": entry["ip"], "matched_signals": matched, "score": round(score, 2)})
            max_score = max(max_score, score)
    return NoveltyReport(
        risk_score=max_score,
        similar_ips=sorted(hits, key=lambda h: -h["score"]),
        method="heuristic",
        notes=("命中已知 IP" if hits else "未命中已知 IP 库"),
    )


def _via_anthropic(text: str) -> NoveltyReport:
    key = os.environ["ANTHROPIC_API_KEY"]
    library_json = json.dumps(
        [{"ip": e["ip"], "signals": e["signals"]} for e in _FINGERPRINT_LIBRARY],
        ensure_ascii=False,
    )
    system = (
        "你是版权检测助手。判断输入文本是否在抄袭、改编或大量借用知名 IP。"
        "返回严格 JSON：{\"risk_score\": 0-1 float, \"similar_ips\": [{\"ip\": str, \"matched_signals\": [str], \"score\": 0-1}], \"notes\": str}\n"
        "评分规则：完全原创=0；少量类似氛围=0.2-0.4；存在独创角色/地名/情节大量重叠=0.7+；近乎复刻=0.9+。\n"
        f"已知 IP 库：{library_json}"
    )
    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7-20260413"),
        "max_tokens": 800,
        "temperature": 0.0,
        "system": system,
        "messages": [{"role": "user", "content": text[:8000]}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    raw = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    parsed = _parse_json_safely(raw)
    return NoveltyReport(
        risk_score=float(parsed.get("risk_score", 0.0)),
        similar_ips=list(parsed.get("similar_ips", [])),
        method="anthropic",
        notes=parsed.get("notes", ""),
    )


def _parse_json_safely(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        # Try grabbing the first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


__all__ = ["novelty_check", "NoveltyReport"]
