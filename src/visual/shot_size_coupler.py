"""V10 §4.2 — Shot-size ↔ emotion ↔ pose coupling.

Mediates between the storyboard layouter and the per-shot generation
prompt, ensuring close-ups happen only on high-emotion beats and that
crowd shots get wider framing.
"""
from __future__ import annotations

from dataclasses import dataclass

# Canonical shot sizes in narrative shorthand
SHOT_SIZES = (
    "extreme_long",   # establishes geography
    "long",
    "medium_long",
    "medium",
    "medium_closeup",
    "closeup",
    "extreme_closeup",
)


@dataclass
class ShotPlanItem:
    shot_size: str
    rationale: str
    camera_movement: str
    angle: str
    duration_s: float


def plan_shot(*, emotion_intensity: int, atmosphere: str | None,
              n_characters: int, prev_shot_size: str | None = None,
              is_climax: bool = False) -> ShotPlanItem:
    intensity = max(1, min(5, int(emotion_intensity)))
    # Crowd scenes go wider
    if n_characters >= 4:
        size = "extreme_long" if n_characters >= 7 else "long"
        movement = "slow dolly" if atmosphere in ("battle", "festive") else "static"
    elif intensity >= 5 or is_climax:
        size = "extreme_closeup"
        movement = "push-in"
    elif intensity == 4:
        size = "closeup"
        movement = "slight push-in"
    elif intensity == 3:
        size = "medium_closeup"
        movement = "static"
    elif intensity == 2:
        size = "medium"
        movement = "subtle pan"
    else:
        size = "medium_long"
        movement = "static"
    # Avoid two extreme close-ups in a row
    if prev_shot_size in ("closeup", "extreme_closeup") and size in ("closeup", "extreme_closeup"):
        size = "medium_closeup"
        movement = "subtle pan"
    angle = "low" if atmosphere in ("battle", "tense", "menacing") else "eye"
    if atmosphere == "tranquil":
        angle = "high"
    duration = 3.0 + intensity * 0.6 + (1.5 if n_characters >= 3 else 0)
    rationale = (
        f"intensity={intensity}, atm={atmosphere or '—'}, "
        f"n_char={n_characters}{', climax' if is_climax else ''}"
    )
    return ShotPlanItem(
        shot_size=size, rationale=rationale,
        camera_movement=movement, angle=angle,
        duration_s=round(duration, 1),
    )


def build_shot_prompt_suffix(item: ShotPlanItem) -> str:
    return (
        f", {item.shot_size.replace('_', ' ')} shot, "
        f"{item.angle} angle, camera {item.camera_movement}, "
        f"{item.duration_s}s duration"
    )


__all__ = ["ShotPlanItem", "plan_shot", "build_shot_prompt_suffix", "SHOT_SIZES"]
