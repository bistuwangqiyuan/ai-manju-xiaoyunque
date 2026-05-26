"""剧情续写 — auto-write next episodes given prior content + character library.

Requirement doc §9 剧情续写：根据已有内容自动生成续集剧情/分集大纲。
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request

_log = logging.getLogger(__name__)


def continue_story(
    *,
    prior_novel: str,
    prior_episodes: list[dict],
    extra_episodes: int = 1,
    direction: str | None = None,
    genre: str = "ancient",
    character_manifests: list[dict] | None = None,
    n_candidates: int = 1,
    foreshadowing: list[str] | None = None,
) -> dict:
    """Return ``{episodes: [...], direction_used, method}`` for ``n_candidates==1``
    or ``{candidates: [{episodes:[...], summary, direction_used}, ...]}`` for
    ``n_candidates>1``.

    V10 §8.1 — supports multi-candidate brainstorming and explicit
    foreshadowing injection (each item in ``foreshadowing`` is woven into
    one of the new episodes).
    """
    if n_candidates and n_candidates > 1:
        return _continue_multi(
            prior_novel=prior_novel, prior_episodes=prior_episodes,
            extra_episodes=extra_episodes, direction=direction, genre=genre,
            character_manifests=character_manifests or [],
            n_candidates=n_candidates, foreshadowing=foreshadowing or [],
        )

    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("FORCE_MOCK_CONTINUATION") != "1":
        try:
            result = _via_anthropic(
                prior_novel, prior_episodes, extra_episodes, direction, genre,
                character_manifests or [],
            )
            if foreshadowing:
                _inject_foreshadowing(result.get("episodes", []), foreshadowing)
            return result
        except Exception as e:
            _log.warning("continuation via anthropic failed: %s", e)
    result = _heuristic(prior_episodes, extra_episodes, direction, genre)
    if foreshadowing:
        _inject_foreshadowing(result.get("episodes", []), foreshadowing)
    return result


def _continue_multi(
    *, prior_novel: str, prior_episodes: list[dict], extra_episodes: int,
    direction: str | None, genre: str, character_manifests: list[dict],
    n_candidates: int, foreshadowing: list[str],
) -> dict:
    """Brainstorm ``n_candidates`` divergent continuations."""
    seeds = [
        direction or "延续上一集结尾的悬念",
        "翻转主角立场或揭露隐藏身份",
        "推进副线、引入新对手或盟友",
        "聚焦情感纠葛与心理转折",
        "围绕单一危机的密集冲突",
    ]
    candidates: list[dict] = []
    for i in range(n_candidates):
        seed = seeds[i % len(seeds)]
        seed_full = f"候选 {i + 1}：{seed}"
        eps = _heuristic(prior_episodes, extra_episodes, seed_full, genre)
        for j, ep in enumerate(eps.get("episodes", [])):
            ep["title"] = f"{ep.get('title', '')}（候选{i + 1}）"
            ep["candidate_index"] = i
        if foreshadowing:
            _inject_foreshadowing(eps.get("episodes", []), foreshadowing)
        candidates.append({
            "candidate_index": i,
            "summary": seed,
            "direction_used": seed_full,
            "episodes": eps.get("episodes", []),
        })
    return {
        "candidates": candidates,
        "n_candidates": n_candidates,
        "method": "multi_heuristic",
        "foreshadowing_used": list(foreshadowing),
    }


def _inject_foreshadowing(episodes: list[dict], foreshadowing: list[str]) -> None:
    """Distribute foreshadowing lines across the generated episodes."""
    if not episodes or not foreshadowing:
        return
    n_eps = len(episodes)
    for idx, fs in enumerate(foreshadowing):
        target = episodes[idx % n_eps]
        existing = target.get("foreshadowing_payload") or []
        existing.append(fs)
        target["foreshadowing_payload"] = existing
        target["synopsis"] = (target.get("synopsis") or "") + f"【伏笔】{fs}"


def _heuristic(
    prior_episodes: list[dict],
    extra_episodes: int,
    direction: str | None,
    genre: str,
) -> dict:
    last_ep_no = max((int(re.sub(r"\D", "", ep.get("episode_id", "ep00") or "0") or 0) for ep in prior_episodes), default=len(prior_episodes))
    base_dir = direction or f"延续上一集结尾的悬念，深化 {genre} 题材的核心冲突。"
    eps = []
    for i in range(extra_episodes):
        n = last_ep_no + i + 1
        eps.append(
            {
                "episode_id": f"ep{n:02d}",
                "title": f"第 {n} 集 · 续",
                "duration_seconds": 75,
                "hook_3s": "开场即抛重磅悬念。",
                "synopsis": f"{base_dir}（episode {n}）",
                "characters_in_episode": [],
                "scenes_in_episode": [],
                "shots": [],
            }
        )
    return {
        "episodes": eps,
        "direction_used": base_dir,
        "method": "heuristic",
    }


def _via_anthropic(
    prior_novel: str,
    prior_episodes: list[dict],
    extra_episodes: int,
    direction: str | None,
    genre: str,
    character_manifests: list[dict],
) -> dict:
    key = os.environ["ANTHROPIC_API_KEY"]
    system = (
        "你是顶级中文短剧编剧。给定剧本与角色库，撰写续集分集 outline。\n"
        "返回严格 JSON：{\"episodes\": [{\"episode_id\": str, \"title\": str, "
        "\"duration_seconds\": int, \"hook_3s\": str, \"synopsis\": str, "
        "\"characters_in_episode\": [str], \"scenes_in_episode\": [str]}], "
        "\"direction_used\": str}\n"
        "约束：episode_id 必须以 ep 开头数字递增；时长 60-90s；钩子前置；保留角色锁定符号"
    )
    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7-20260413"),
        "max_tokens": 4000,
        "temperature": 0.7,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"题材：{genre}\n续写方向：{direction or '(用户未指定)'}\n"
                    f"续写集数：{extra_episodes}\n"
                    f"现有分集：{json.dumps(prior_episodes[:10], ensure_ascii=False)[:2000]}\n"
                    f"角色库：{json.dumps([c.get('name_zh') or c.get('char_id') for c in character_manifests], ensure_ascii=False)}\n"
                    f"原作节选：{prior_novel[:1500]}"
                ),
            }
        ],
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    raw = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    parsed = _parse_json_safely(raw) or _heuristic(prior_episodes, extra_episodes, direction, genre)
    parsed["method"] = "anthropic"
    return parsed


def _parse_json_safely(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


__all__ = ["continue_story"]
