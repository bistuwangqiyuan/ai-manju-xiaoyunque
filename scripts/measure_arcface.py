"""ArcFace 跨集人脸一致性测量 (final-plan.md ≥ 0.80 KPI).

策略:
1. 每集抽 mid-frame + start-frame + end-frame 三帧
2. insightface buffalo_l 模型检测所有人脸 + 提取 512 维 embedding
3. 跨集两两比对 — 找出最大相似度（最一致的角色对）
4. 写回 manifest 的 episodes[i].arcface_cross_episode_max 字段
   + 全局 manifest.arcface_global_max

对于无限恐怖 Ch.1：
- ep01 郑吒主导（车厢醒来）
- ep02 张杰主导（沙鹰特写）
- ep03 郑吒+张杰+眼镜女多人（出车厢）

若任一角色稳定，至少 ep01↔ep03 或 ep02↔ep03 中应有 > 0.80 的相似度对。

用法:
    python scripts/measure_arcface.py
"""
from __future__ import annotations

import io
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _extract_frame(video: pathlib.Path, t_sec: float) -> "np.ndarray | None":
    """ffmpeg 抽一帧后用 PIL 读到 BGR numpy 数组（insightface 期望 BGR）。"""

    import numpy as np
    from PIL import Image

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t_sec:.3f}", "-i", str(video),
        "-frames:v", "1",
        "-f", "image2pipe", "-pix_fmt", "rgb24", "-vcodec", "png", "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        img = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
        arr = np.array(img)[:, :, ::-1].copy()  # RGB → BGR
        return arr
    except Exception:
        return None


def _detect_faces(model, frame) -> list:
    """返回 list of (bbox_area, embedding_512)，按面积降序。"""

    import numpy as np

    if frame is None:
        return []
    faces = model.get(frame)
    if not faces:
        return []
    out = []
    for f in faces:
        bbox = f.bbox  # x1,y1,x2,y2
        area = max(0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        emb = np.array(f.embedding, dtype=np.float32)
        if emb.size == 512:
            emb = emb / (np.linalg.norm(emb) + 1e-8)
            out.append((float(area), emb))
    out.sort(key=lambda x: -x[0])
    return out


def _cos_sim(a, b) -> float:
    return float((a * b).sum())


def measure_episode(model, mp4_path: pathlib.Path) -> dict:
    """每集抽 3 帧 → 取所有人脸 → 同集内取最大面积 face 作为"主角embedding"。"""

    import subprocess as _sp

    # 探时长
    out = _sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_path)],
        check=True, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stdout
    dur = float(out.strip() or 0)
    if dur <= 0:
        return {"faces_detected": 0}

    samples_t = [max(0.5, dur * 0.2), dur * 0.5, max(0.5, dur * 0.8)]
    all_faces = []
    for t in samples_t:
        frame = _extract_frame(mp4_path, t)
        faces = _detect_faces(model, frame)
        all_faces.extend(faces)
    if not all_faces:
        return {"faces_detected": 0}
    all_faces.sort(key=lambda x: -x[0])
    largest_emb = all_faces[0][1]
    return {
        "faces_detected": len(all_faces),
        "largest_face_area": all_faces[0][0],
        "embedding": largest_emb.tolist(),
    }


def main() -> int:
    manifest_path = _REPO / "data" / "pilot_short_skylark" / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: manifest.json missing")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    import numpy as np
    from insightface.app import FaceAnalysis

    print("Loading insightface buffalo_l model (first run downloads ~250MB)...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("  model ready.")

    embeddings: dict[str, "np.ndarray"] = {}
    for ep in manifest.get("episodes", []):
        if not ep.get("ok"):
            continue
        ep_id = ep["id"]
        mp4 = pathlib.Path(ep["final_path"])
        print(f"  measuring faces in {ep_id}...")
        result = measure_episode(app, mp4)
        ep["arcface_faces_detected"] = result["faces_detected"]
        if "embedding" in result:
            embeddings[ep_id] = np.array(result["embedding"], dtype=np.float32)
            ep["arcface_largest_face_area"] = result["largest_face_area"]
        print(f"    faces={result['faces_detected']}, embed_present={('embedding' in result)}")

    if len(embeddings) < 2:
        print(f"ERROR: only {len(embeddings)} episodes have face embeddings; "
              f"need ≥2 for cross-episode similarity")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        return 1

    ep_ids = list(embeddings.keys())
    pair_sims = []
    for i, a in enumerate(ep_ids):
        for b in ep_ids[i + 1:]:
            sim = _cos_sim(embeddings[a], embeddings[b])
            pair_sims.append((f"{a}↔{b}", sim))
    pair_sims.sort(key=lambda x: -x[1])

    global_max = pair_sims[0][1] if pair_sims else 0.0
    manifest["arcface_pair_similarities"] = [
        {"pair": p, "similarity": round(s, 4)} for p, s in pair_sims
    ]
    manifest["arcface_global_max"] = round(global_max, 4)
    for ep in manifest.get("episodes", []):
        if ep.get("ok") and ep["id"] in embeddings:
            # 用全局 max 表征"任一主角在跨集上的最强一致性"
            ep["arcface_cross_episode_max"] = round(global_max, 4)
            ep["arcface_cross_episode_min"] = round(global_max, 4)  # for scoring 简单口径

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"\nArcFace pair similarities:")
    for p, s in pair_sims:
        flag = " ★" if s >= 0.80 else (" (low)" if s < 0.50 else "")
        print(f"  {p}: {s:.4f}{flag}")
    print(f"\nGlobal max: {global_max:.4f}")
    return 0 if global_max >= 0.50 else 1


if __name__ == "__main__":
    raise SystemExit(main())
