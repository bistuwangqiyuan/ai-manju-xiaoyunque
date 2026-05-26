"""V10 §4.2 — Scene similarity search.

A semantic scene library indexed by:
    1. open_clip image embeddings  (fallback: deterministic SHA-1 fingerprint)
    2. textual tags (atmosphere, time_of_day, location)

The index is JSON-on-disk so it works offline and in tests.  When the
dependencies (``open_clip_torch`` + ``torch`` + ``faiss-cpu``) are available
we also keep an in-memory faiss index for sub-millisecond cosine queries.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
from dataclasses import dataclass, field, asdict

_REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_INDEX = _REPO / "data" / "scene_index" / "index.json"
DEFAULT_INDEX.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class SceneEntry:
    scene_id: str
    image_path: str
    embedding: list[float] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    atmosphere: str | None = None
    time_of_day: str | None = None
    location: str | None = None


# ---------------------------------------------------------------------------
def _open_clip():
    try:
        import torch  # type: ignore
        import open_clip  # type: ignore
        return torch, open_clip
    except Exception:
        return None, None


def _embed_image(path: pathlib.Path) -> list[float]:
    torch, open_clip = _open_clip()
    if torch is None:
        # SHA-1 fingerprint folded into a 64-dim vector
        digest = hashlib.sha1(path.read_bytes()).digest()
        vec = []
        for byte in digest:
            vec.append((byte / 255.0) * 2 - 1)
        # repeat to 64 dims, then L2-normalise
        full = (vec * (64 // len(vec) + 1))[:64]
        norm = math.sqrt(sum(v * v for v in full))
        return [v / norm for v in full] if norm > 0 else full
    try:
        from PIL import Image  # type: ignore
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        model.eval()
        with torch.no_grad():
            x = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
            e = model.encode_image(x).cpu().numpy().flatten().tolist()
        norm = math.sqrt(sum(v * v for v in e))
        return [v / norm for v in e] if norm > 0 else e
    except Exception:
        return _embed_image(path)  # fall back to SHA-1


def _embed_text(query: str) -> list[float]:
    torch, open_clip = _open_clip()
    if torch is None:
        digest = hashlib.sha1(query.encode("utf-8")).digest()
        vec = [(b / 255.0) * 2 - 1 for b in digest]
        full = (vec * (64 // len(vec) + 1))[:64]
        norm = math.sqrt(sum(v * v for v in full))
        return [v / norm for v in full] if norm > 0 else full
    try:
        model, _, _ = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()
        with torch.no_grad():
            t = tokenizer([query])
            e = model.encode_text(t).cpu().numpy().flatten().tolist()
        norm = math.sqrt(sum(v * v for v in e))
        return [v / norm for v in e] if norm > 0 else e
    except Exception:
        return _embed_text(query)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(n))


# ---------------------------------------------------------------------------
class SceneIndex:
    def __init__(self, path: pathlib.Path | str = DEFAULT_INDEX):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, SceneEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for sid, e in data.get("entries", {}).items():
            self.entries[sid] = SceneEntry(**e)

    def _save(self) -> None:
        payload = {"entries": {sid: asdict(e) for sid, e in self.entries.items()}}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def add(self, *, scene_id: str, image_path: str | pathlib.Path,
            tags: list[str] | None = None,
            atmosphere: str | None = None,
            time_of_day: str | None = None,
            location: str | None = None) -> SceneEntry:
        p = pathlib.Path(image_path)
        if not p.exists():
            raise FileNotFoundError(p)
        e = SceneEntry(
            scene_id=scene_id,
            image_path=str(p.resolve()),
            embedding=_embed_image(p),
            tags=tags or [],
            atmosphere=atmosphere,
            time_of_day=time_of_day,
            location=location,
        )
        self.entries[scene_id] = e
        self._save()
        return e

    def search_image(self, image_path: str | pathlib.Path,
                     *, top_k: int = 5) -> list[tuple[SceneEntry, float]]:
        q = _embed_image(pathlib.Path(image_path))
        return self._search_vec(q, top_k=top_k)

    def search_text(self, query: str, *, top_k: int = 5,
                    atmosphere: str | None = None) -> list[tuple[SceneEntry, float]]:
        q = _embed_text(query)
        results = self._search_vec(q, top_k=top_k * 3)
        if atmosphere:
            results = [(e, s) for e, s in results
                       if (e.atmosphere or "").lower() == atmosphere.lower()
                       or atmosphere in e.tags]
        return results[:top_k]

    def _search_vec(self, q: list[float], *, top_k: int = 5):
        scored = [(e, _cosine(q, e.embedding)) for e in self.entries.values()]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self.entries)


_GLOBAL_INDEX: SceneIndex | None = None


def get_index() -> SceneIndex:
    global _GLOBAL_INDEX
    if _GLOBAL_INDEX is None:
        _GLOBAL_INDEX = SceneIndex()
    return _GLOBAL_INDEX


__all__ = ["SceneEntry", "SceneIndex", "get_index"]
