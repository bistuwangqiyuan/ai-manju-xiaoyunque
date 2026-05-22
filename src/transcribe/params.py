"""Per-file redraw parameter schema.

The batch UI lets users set defaults for the whole batch, then override per
file. The schema below is the union of every knob we expose; engines pick
what they understand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MultiModalRefs:
    """Reference inputs (requirement doc §12 多模态融合)."""

    image_urls: list[str] = field(default_factory=list)
    text_prompt: str = ""
    style_reference_url: str | None = None
    character_ids: list[str] = field(default_factory=list)
    forbidden_words: list[str] = field(default_factory=list)
    forbidden_elements: list[str] = field(default_factory=list)


@dataclass
class RedrawParams:
    """One redraw item's effective parameters."""

    # core
    style: str = "ancient_3d_guoman"
    genre: str = "ancient"
    aspect_ratio: str = "9:16"

    # control
    reference_weight: float = 0.85
    structure_lock: bool = True
    detail_enhance: float = 0.5      # 0–1
    color_grade: str = "auto"        # auto / cool / warm / teal_orange
    region_mask_url: str | None = None  # local edit mask
    seed: int | None = None

    # quality loop
    pass_threshold: float = 7.5
    max_iter: int = 2

    # multi-modal refs
    refs: MultiModalRefs = field(default_factory=MultiModalRefs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "genre": self.genre,
            "aspect_ratio": self.aspect_ratio,
            "reference_weight": self.reference_weight,
            "structure_lock": self.structure_lock,
            "detail_enhance": self.detail_enhance,
            "color_grade": self.color_grade,
            "region_mask_url": self.region_mask_url,
            "seed": self.seed,
            "pass_threshold": self.pass_threshold,
            "max_iter": self.max_iter,
            "refs": {
                "image_urls": list(self.refs.image_urls),
                "text_prompt": self.refs.text_prompt,
                "style_reference_url": self.refs.style_reference_url,
                "character_ids": list(self.refs.character_ids),
                "forbidden_words": list(self.refs.forbidden_words),
                "forbidden_elements": list(self.refs.forbidden_elements),
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RedrawParams":
        if not d:
            return cls()
        refs_d = d.get("refs") or {}
        return cls(
            style=d.get("style", "ancient_3d_guoman"),
            genre=d.get("genre", "ancient"),
            aspect_ratio=d.get("aspect_ratio", "9:16"),
            reference_weight=float(d.get("reference_weight", 0.85)),
            structure_lock=bool(d.get("structure_lock", True)),
            detail_enhance=float(d.get("detail_enhance", 0.5)),
            color_grade=d.get("color_grade", "auto"),
            region_mask_url=d.get("region_mask_url"),
            seed=d.get("seed"),
            pass_threshold=float(d.get("pass_threshold", 7.5)),
            max_iter=int(d.get("max_iter", 2)),
            refs=MultiModalRefs(
                image_urls=list(refs_d.get("image_urls", []) or []),
                text_prompt=refs_d.get("text_prompt", ""),
                style_reference_url=refs_d.get("style_reference_url"),
                character_ids=list(refs_d.get("character_ids", []) or []),
                forbidden_words=list(refs_d.get("forbidden_words", []) or []),
                forbidden_elements=list(refs_d.get("forbidden_elements", []) or []),
            ),
        )


__all__ = ["RedrawParams", "MultiModalRefs"]
