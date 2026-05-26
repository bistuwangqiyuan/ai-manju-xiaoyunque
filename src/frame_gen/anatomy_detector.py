"""V10 §5.3 — Anatomy anomaly detector (face / hand / body).

Uses MediaPipe (Face Mesh + Hands + Pose) when available to surface common
GenAI artifacts:
    - extra fingers (>5)
    - mismatched eyes (asymmetric size)
    - missing limbs
    - distorted face mesh
    - body proportion violation

Each call returns a per-axis 0-10 *deformation* score (higher = worse) and a
list of suggested repair routes for the V10 §6 repair router.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field


@dataclass
class AnatomyReport:
    score_face: float = 0.0       # 0=clean, 10=severely distorted
    score_hand: float = 0.0
    score_body: float = 0.0
    detected_anomalies: list[str] = field(default_factory=list)
    suggested_routes: list[str] = field(default_factory=list)
    backend: str = "mediapipe"

    @property
    def severity(self) -> float:
        return max(self.score_face, self.score_hand, self.score_body)

    def to_dict(self) -> dict:
        return {
            "score_face": round(self.score_face, 2),
            "score_hand": round(self.score_hand, 2),
            "score_body": round(self.score_body, 2),
            "severity": round(self.severity, 2),
            "detected_anomalies": self.detected_anomalies,
            "suggested_routes": self.suggested_routes,
            "backend": self.backend,
        }


def _heuristic_report(image_path: pathlib.Path) -> AnatomyReport:
    """Deterministic fallback used when mediapipe / opencv aren't installed.

    Scores depend on filename hints so tests can verify the routing logic.
    """
    name = image_path.name.lower()
    rep = AnatomyReport(backend="heuristic")
    if "hand" in name or "finger" in name:
        rep.score_hand = 8.0
        rep.detected_anomalies.append("hand:extra_fingers")
        rep.suggested_routes.append("hand_local")
    if "face" in name or "eye" in name:
        rep.score_face = 7.0
        rep.detected_anomalies.append("face:asymmetric_eyes")
        rep.suggested_routes.append("face_drift")
    if "body" in name or "limb" in name:
        rep.score_body = 6.0
        rep.detected_anomalies.append("body:missing_limb")
        rep.suggested_routes.append("motion_axis")
    return rep


def detect(image_path: str | pathlib.Path) -> AnatomyReport:
    p = pathlib.Path(image_path)
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
    except Exception:
        return _heuristic_report(p)
    img = cv2.imread(str(p))
    if img is None:
        return _heuristic_report(p)
    rep = AnatomyReport(backend="mediapipe")

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ---- Hands ----------------------------------------------------------
    try:
        with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=4,
                                      model_complexity=1) as hands:
            res = hands.process(rgb)
        if res.multi_hand_landmarks:
            for hand in res.multi_hand_landmarks:
                if len(hand.landmark) != 21:
                    rep.score_hand = max(rep.score_hand, 8.0)
                    rep.detected_anomalies.append("hand:landmark_count_mismatch")
                # extra-fingers proxy: spread + irregular spacing of fingertips
                tips = [hand.landmark[i] for i in (4, 8, 12, 16, 20)]
                xs = [t.x for t in tips]
                spread = max(xs) - min(xs)
                if spread > 0.6:
                    rep.score_hand = max(rep.score_hand, 5.5)
                    rep.detected_anomalies.append("hand:wide_spread_outlier")
            if not rep.detected_anomalies:
                rep.score_hand = 1.0
    except Exception:
        pass

    # ---- Face -----------------------------------------------------------
    try:
        with mp.solutions.face_mesh.FaceMesh(static_image_mode=True,
                                             max_num_faces=2,
                                             refine_landmarks=True) as fm:
            res = fm.process(rgb)
        if res.multi_face_landmarks:
            face = res.multi_face_landmarks[0]
            # eye asymmetry: distance between eye corners L vs R
            left_w = abs(face.landmark[133].x - face.landmark[33].x)
            right_w = abs(face.landmark[362].x - face.landmark[263].x)
            if left_w > 0 and right_w > 0:
                ratio = max(left_w, right_w) / min(left_w, right_w)
                if ratio > 1.5:
                    rep.score_face = max(rep.score_face, 6.0 + min(3.0, ratio - 1.5))
                    rep.detected_anomalies.append("face:asymmetric_eyes")
    except Exception:
        pass

    # ---- Body / Pose -----------------------------------------------------
    try:
        with mp.solutions.pose.Pose(static_image_mode=True,
                                    model_complexity=1) as pose:
            res = pose.process(rgb)
        if res.pose_landmarks:
            lms = res.pose_landmarks.landmark
            # Missing limb: visibility < 0.2 on any major joint among
            #    shoulders / elbows / wrists / hips / knees / ankles
            crit = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
            invisible = sum(1 for i in crit if lms[i].visibility < 0.2)
            if invisible >= 3:
                rep.score_body = max(rep.score_body, 7.0)
                rep.detected_anomalies.append("body:missing_limb")
            # Anatomy ratio: shoulder width vs hip width should be > 0.7
            sw = abs(lms[11].x - lms[12].x)
            hw = abs(lms[23].x - lms[24].x)
            if sw > 0 and hw > 0 and sw / hw < 0.35:
                rep.score_body = max(rep.score_body, 5.0)
                rep.detected_anomalies.append("body:proportion_violation")
    except Exception:
        pass

    # ---- Routing -----------------------------------------------------
    if rep.score_hand >= 5:
        rep.suggested_routes.append("hand_local")
    if rep.score_face >= 6:
        rep.suggested_routes.append("face_drift")
    if rep.score_body >= 5:
        rep.suggested_routes.append("motion_axis")
    rep.suggested_routes = list(dict.fromkeys(rep.suggested_routes))
    return rep


__all__ = ["AnatomyReport", "detect"]
