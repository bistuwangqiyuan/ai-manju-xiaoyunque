"""V10 §7.1 — Voice library loader & per-line voice resolver.

Loads ``config/voices.yaml`` once, exposes:

    list_roles()                       -> list of role keys with labels
    get_role(role)                     -> RoleConfig dataclass
    resolve(role, emotion, provider?)  -> ResolvedVoice — provider, voice_id,
                                          provider-specific emotion tag
    auto_speed_volume(emotion, intensity) -> (speed, vol)
        Maps our emotion + 0-1 intensity into TTS speed/vol modifiers.

The library is provider-agnostic; downstream callers feed the result into
``shell5_post_production.tts_doubao_icl`` / ``tts_elevenlabs_intl`` /
``tts_minimax``.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_VOICES_YAML = _REPO / "config" / "voices.yaml"


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    """Tolerant loader — uses pyyaml if available, else a tiny custom parser."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return _mini_yaml_parse(path.read_text(encoding="utf-8"))


def _mini_yaml_parse(text: str) -> dict[str, Any]:
    """Tiny YAML subset parser sufficient for voices.yaml structure."""
    import re

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    def _coerce(val: str) -> Any:
        val = val.strip()
        if val == "" or val.lower() in ("null", "~"):
            return None
        if val.lower() in ("true", "false"):
            return val.lower() == "true"
        if re.fullmatch(r"-?\d+", val):
            return int(val)
        if re.fullmatch(r"-?\d+\.\d+", val):
            return float(val)
        # list shorthand: [a, b, c]
        m = re.fullmatch(r"\[(.*)\]", val)
        if m:
            inner = m.group(1).strip()
            if not inner:
                return []
            return [_coerce(x) for x in inner.split(",")]
        return val.strip().strip('"').strip("'")

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        stripped = line.strip()

        if stripped.startswith("- "):
            item_text = stripped[2:].strip()
            if isinstance(parent, list):
                if ":" in item_text:
                    key, _, val = item_text.partition(":")
                    obj: dict[str, Any] = {key.strip(): _coerce(val)}
                    parent.append(obj)
                    stack.append((indent + 2, obj))
                else:
                    parent.append(_coerce(item_text))
            continue
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val_clean = val.strip()
        if val_clean == "":
            # Container — peek next line to decide list vs dict
            new: list | dict = {}  # default
            if isinstance(parent, dict):
                parent[key] = new
            stack.append((indent, new))
        else:
            value = _coerce(val_clean)
            if isinstance(parent, dict):
                parent[key] = value

    return root


@dataclass
class VoiceEndpoint:
    provider: str
    voice_id: str


@dataclass
class RoleConfig:
    key: str
    label: str
    age_range: tuple[int, int]
    gender: str
    primary: VoiceEndpoint
    fallback: list[VoiceEndpoint] = field(default_factory=list)
    emotion_map: dict[str, str] = field(default_factory=dict)


@dataclass
class ResolvedVoice:
    role: str
    provider: str
    voice_id: str
    emotion_native: str
    speed: float
    vol: float
    fallback_chain: list[VoiceEndpoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role, "provider": self.provider, "voice_id": self.voice_id,
            "emotion_native": self.emotion_native, "speed": self.speed, "vol": self.vol,
            "fallback_chain": [{"provider": e.provider, "voice_id": e.voice_id}
                               for e in self.fallback_chain],
        }


class VoiceLibrary:
    def __init__(self, path: pathlib.Path | str | None = None):
        self.path = pathlib.Path(path) if path else _VOICES_YAML
        self._data: dict[str, Any] = {}
        self._roles: dict[str, RoleConfig] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            raise FileNotFoundError(f"voices.yaml missing at {self.path}")
        self._data = _load_yaml(self.path)
        for key, conf in (self._data.get("roles") or {}).items():
            primary_conf = conf.get("primary") or {}
            fb_conf = conf.get("fallback") or []
            self._roles[key] = RoleConfig(
                key=key,
                label=conf.get("label") or key,
                age_range=tuple(conf.get("age_range") or [0, 0])[:2],  # type: ignore
                gender=conf.get("gender") or "unknown",
                primary=VoiceEndpoint(
                    provider=primary_conf.get("provider", "doubao"),
                    voice_id=primary_conf.get("voice_id", ""),
                ),
                fallback=[
                    VoiceEndpoint(provider=f.get("provider", "doubao"),
                                  voice_id=f.get("voice_id", ""))
                    for f in fb_conf
                ],
                emotion_map=conf.get("emotion_map") or {},
            )
        self._loaded = True

    def list_roles(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return [
            {"key": r.key, "label": r.label, "gender": r.gender,
             "age_range": list(r.age_range)}
            for r in self._roles.values()
        ]

    def get_role(self, role: str) -> RoleConfig:
        self._ensure_loaded()
        if role not in self._roles:
            raise KeyError(f"Unknown voice role: {role}; available: {list(self._roles)}")
        return self._roles[role]

    def resolve(self, role: str, emotion: str = "neutral",
                provider: str | None = None,
                intensity: float = 0.5) -> ResolvedVoice:
        cfg = self.get_role(role)
        chain: list[VoiceEndpoint] = [cfg.primary] + list(cfg.fallback)
        if provider:
            for ep in chain:
                if ep.provider == provider:
                    chain = [ep] + [e for e in chain if e is not ep]
                    break
        chosen = chain[0]
        native = cfg.emotion_map.get(emotion, emotion)
        speed, vol = auto_speed_volume(emotion, intensity)
        return ResolvedVoice(
            role=role, provider=chosen.provider, voice_id=chosen.voice_id,
            emotion_native=native, speed=speed, vol=vol,
            fallback_chain=chain[1:],
        )

    @property
    def default_lufs(self) -> float:
        self._ensure_loaded()
        return float(self._data.get("default_lufs", -14.0))


def auto_speed_volume(emotion: str, intensity: float) -> tuple[float, float]:
    """Map our 7-dim emotion + 0..1 intensity into TTS speed/volume modifiers.

    Speed and vol are relative multipliers (1.0 == neutral). Numbers tuned
    against need.md §7.1 quality bar.
    """
    intensity = max(0.0, min(1.0, intensity))
    base_speed, base_vol = 1.0, 1.0
    delta_speed = 0.0
    delta_vol = 0.0
    e = (emotion or "").lower()
    if e in ("angry", "fury"):
        delta_speed = +0.10
        delta_vol = +0.30
    elif e in ("happy", "joy", "surprised", "gasp"):
        delta_speed = +0.07
        delta_vol = +0.15
    elif e in ("sad", "cry", "lament"):
        delta_speed = -0.12
        delta_vol = -0.20
    elif e in ("fearful", "tremble"):
        delta_speed = -0.05
        delta_vol = -0.10
    elif e in ("disgusted", "scorn", "cold"):
        delta_speed = -0.03
        delta_vol = -0.05
    speed = round(base_speed + delta_speed * intensity, 3)
    vol = round(base_vol + delta_vol * intensity, 3)
    speed = max(0.6, min(1.5, speed))
    vol = max(0.5, min(1.5, vol))
    return speed, vol


_GLOBAL: VoiceLibrary | None = None


def get_library() -> VoiceLibrary:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = VoiceLibrary()
    return _GLOBAL


__all__ = [
    "VoiceEndpoint", "RoleConfig", "ResolvedVoice", "VoiceLibrary",
    "get_library", "auto_speed_volume",
]
