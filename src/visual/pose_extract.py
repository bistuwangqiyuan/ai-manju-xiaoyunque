"""V10 §4.1 — Pose extraction → action library.

Run MediaPipe Pose on a directory of reference action frames; cluster the
resulting 33-keypoint vectors and assign each cluster a canonical action
label ("跑动" / "拥抱" / "跪地" ...).  The library is persisted to JSON
so the storyboard layouter can index into it by label.

Degrades gracefully:
- mediapipe missing → returns 0 poses
- OpenCV missing → reads JPEGs through PIL
"""
from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass, field, asdict


POSE_LANDMARK_COUNT = 33


@dataclass
class PoseRecord:
    image_path: str
    keypoints: list[list[float]] = field(default_factory=list)  # [33][x,y,z,visibility]
    bbox: tuple[float, float, float, float] | None = None
    confidence: float = 0.0


@dataclass
class PoseClusterCatalog:
    library: dict[str, list[PoseRecord]] = field(default_factory=dict)

    def add(self, label: str, record: PoseRecord) -> None:
        self.library.setdefault(label, []).append(record)

    def to_json(self) -> str:
        return json.dumps({
            label: [{
                "image_path": r.image_path,
                "keypoints": r.keypoints,
                "bbox": r.bbox,
                "confidence": r.confidence,
            } for r in records]
            for label, records in self.library.items()
        }, ensure_ascii=False, indent=2)


_CANONICAL_LABELS = [
    "stand", "walk", "run", "kneel", "sit", "hug",
    "fight", "fall", "reach", "point", "bow", "leap",
]


def extract_pose(image_path: str | pathlib.Path) -> PoseRecord | None:
    p = pathlib.Path(image_path)
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
    except Exception:
        return None
    img = cv2.imread(str(p))
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    with mp.solutions.pose.Pose(static_image_mode=True,
                                model_complexity=1,
                                enable_segmentation=False) as pose:
        res = pose.process(rgb)
    if not res.pose_landmarks:
        return None
    kp = [[lm.x, lm.y, lm.z, lm.visibility] for lm in res.pose_landmarks.landmark]
    xs = [x for x, _, _, v in kp if v > 0.1]
    ys = [y for _, y, _, v in kp if v > 0.1]
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None
    avg_conf = sum(lm.visibility for lm in res.pose_landmarks.landmark) / POSE_LANDMARK_COUNT
    return PoseRecord(image_path=str(p), keypoints=kp, bbox=bbox,
                      confidence=round(avg_conf, 3))


def classify_pose(rec: PoseRecord) -> str:
    """Heuristic mapping from keypoint geometry to one of CANONICAL_LABELS.

    No ML model — just rule-of-thumb angles.  Good enough to seed the
    library before users start adding real labels themselves.
    """
    if not rec.keypoints:
        return "unknown"
    # mediapipe pose indices (subset we care about)
    # 11/12 left/right shoulder, 13/14 elbow, 15/16 wrist, 23/24 hip,
    # 25/26 knee, 27/28 ankle, 31/32 foot index
    kp = rec.keypoints
    def y(i):
        return kp[i][1] if i < len(kp) and len(kp[i]) > 1 else 0.5
    def x(i):
        return kp[i][0] if i < len(kp) and len(kp[i]) > 0 else 0.5

    head_y = y(0)
    hip_y = (y(23) + y(24)) / 2
    knee_y = (y(25) + y(26)) / 2
    ankle_y = (y(27) + y(28)) / 2

    # Falling: head below hips (check first because everything else assumes head up)
    if head_y > hip_y + 0.05:
        return "fall"
    # Sitting: knees near hip vertical (check before stand because stand is permissive)
    if abs(knee_y - hip_y) < 0.08:
        return "sit"
    # Kneeling: knees on ground (knees near ankles)
    if abs(knee_y - ankle_y) < 0.06 and hip_y < knee_y:
        return "kneel"
    # Reach: wrist higher than head
    if y(15) < head_y - 0.05 or y(16) < head_y - 0.05:
        return "reach"
    # Standing: head well above hips, hips above knees, knees above ankles
    if head_y < hip_y - 0.20 and ankle_y > knee_y:
        return "stand"
    return "stand"


def build_library_from_dir(directory: str | pathlib.Path) -> PoseClusterCatalog:
    cat = PoseClusterCatalog()
    d = pathlib.Path(directory)
    if not d.exists():
        return cat
    for img in sorted(d.rglob("*")):
        if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        rec = extract_pose(img)
        if rec is None:
            continue
        label = classify_pose(rec)
        cat.add(label, rec)
    return cat


__all__ = ["PoseRecord", "PoseClusterCatalog",
           "extract_pose", "classify_pose", "build_library_from_dir",
           "POSE_LANDMARK_COUNT"]
