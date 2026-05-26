"""V10 §4.1 — Expression / framing router.

Given the dominant emotion of a dialogue line plus the surrounding atmosphere,
pick the right facial expression, body posture, and shot size for the
upcoming generation request.
"""
from __future__ import annotations

from dataclasses import dataclass

EMOTION_TO_FACE = {
    "joyful": "bright smile, eyes slightly squinted, raised cheeks",
    "sad": "downturned lips, glistening eyes, lowered eyebrows",
    "angry": "furrowed brow, clenched jaw, tight lips",
    "fearful": "wide eyes, parted lips, tense neck",
    "loving": "soft gaze, gentle smile, slightly tilted head",
    "cold": "neutral mouth, narrowed eyes, raised chin",
    "questioning": "slightly raised eyebrow, parted lips, tilted head",
    "emphatic": "intense eye contact, parted lips, leaning forward",
    "neutral": "relaxed expression, soft gaze",
}

EMOTION_TO_POSE = {
    "joyful": "open arms gesture, weight on front foot",
    "sad": "shoulders slumped, head down",
    "angry": "fists clenched, leaning forward",
    "fearful": "arms drawn in, half-step back",
    "loving": "reaching forward, palm open",
    "cold": "arms crossed, weight back",
    "questioning": "hand at chin or gesturing palm-up",
    "emphatic": "extended arm, finger pointing",
    "neutral": "natural standing pose",
}

# Shot size by intensity (1–5)
INTENSITY_TO_SHOT = {
    1: "long shot",
    2: "medium shot",
    3: "medium close-up",
    4: "close-up",
    5: "extreme close-up",
}


@dataclass
class ExpressionPlan:
    emotion: str
    intensity: int
    face_prompt: str
    pose_prompt: str
    shot_size: str
    camera_angle: str
    framing_prompt: str


def route(emotion: str, intensity: int = 3,
          atmosphere: str | None = None,
          line_text: str | None = None) -> ExpressionPlan:
    e = (emotion or "neutral").lower()
    inten = max(1, min(5, int(intensity)))
    face = EMOTION_TO_FACE.get(e, EMOTION_TO_FACE["neutral"])
    pose = EMOTION_TO_POSE.get(e, EMOTION_TO_POSE["neutral"])
    shot = INTENSITY_TO_SHOT[inten]
    angle = _camera_angle(e, atmosphere)
    framing = (
        f"{shot}, {angle}, focus on character face, soft depth of field"
        if inten >= 3 else
        f"{shot}, {angle}, full character visible, gentle composition"
    )
    return ExpressionPlan(
        emotion=e, intensity=inten,
        face_prompt=face, pose_prompt=pose,
        shot_size=shot, camera_angle=angle,
        framing_prompt=framing,
    )


def _camera_angle(emotion: str, atmosphere: str | None) -> str:
    if emotion in ("angry", "emphatic"):
        return "slight low angle"
    if emotion == "sad":
        return "slight high angle"
    if emotion == "fearful":
        return "dutch angle"
    if (atmosphere or "").lower() in ("tense", "悬疑", "诡谲"):
        return "low angle"
    return "eye-level angle"


def build_full_prompt(*, base_character_prompt: str, plan: ExpressionPlan,
                      style_lock: str = "", scene_setting: str = "") -> str:
    parts = [base_character_prompt]
    if plan.face_prompt:
        parts.append(plan.face_prompt)
    if plan.pose_prompt:
        parts.append(plan.pose_prompt)
    if plan.framing_prompt:
        parts.append(plan.framing_prompt)
    if scene_setting:
        parts.append(scene_setting)
    if style_lock:
        parts.append(style_lock)
    return ", ".join(p for p in parts if p)


__all__ = ["ExpressionPlan", "route", "build_full_prompt",
           "EMOTION_TO_FACE", "EMOTION_TO_POSE", "INTENSITY_TO_SHOT"]
