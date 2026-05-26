"""V10 §4.1 — Costume / climate mapping.

Given an atmosphere ("happy", "tense", "battle", "winter night", ...) returns
an *additive* costume modifier dict that can be appended to the base character
prompt without breaking the existing 11-wardrobe presets.
"""
from __future__ import annotations

from dataclasses import dataclass

ATMOSPHERE_TO_COSTUME = {
    "joyful":  {"color_tweak": "bright tones, light fabric", "accessories": "fresh flowers, ribbons"},
    "sad":     {"color_tweak": "muted blue / gray, soft fabric", "accessories": "single pendant"},
    "tense":   {"color_tweak": "deep crimson / black", "accessories": "leather strap, weapons holstered"},
    "battle":  {"color_tweak": "armoured tones, scuffed", "accessories": "sword on back, armor pieces"},
    "romantic":{"color_tweak": "soft pink / cream", "accessories": "silk scarf, delicate jewellery"},
    "night":   {"color_tweak": "indigo / midnight tones", "accessories": "subtle silver embroidery"},
    "rain":    {"color_tweak": "wet, slightly darker", "accessories": "wet hair, cloak"},
    "winter":  {"color_tweak": "fur trim, layered", "accessories": "scarf, gloves"},
    "summer":  {"color_tweak": "linen, breathable", "accessories": "fan, light sandals"},
    "luxury":  {"color_tweak": "gold thread, brocade", "accessories": "jade ornaments, headdress"},
}


@dataclass
class CostumeAdjustment:
    base_costume_id: str
    color_tweak: str
    accessories: str
    full_modifier: str


def adjust(*, base_costume_id: str, atmosphere: str) -> CostumeAdjustment:
    atm = (atmosphere or "neutral").lower()
    rec = ATMOSPHERE_TO_COSTUME.get(atm)
    if rec is None:
        for key, v in ATMOSPHERE_TO_COSTUME.items():
            if key in atm:
                rec = v
                break
    if rec is None:
        rec = {"color_tweak": "neutral palette", "accessories": ""}
    modifier = ", ".join(filter(None, [rec["color_tweak"], rec["accessories"]]))
    return CostumeAdjustment(
        base_costume_id=base_costume_id,
        color_tweak=rec["color_tweak"],
        accessories=rec["accessories"],
        full_modifier=modifier,
    )


def merge_into_prompt(prompt: str, *, base_costume_id: str, atmosphere: str) -> str:
    adj = adjust(base_costume_id=base_costume_id, atmosphere=atmosphere)
    if not adj.full_modifier:
        return prompt
    return f"{prompt}, wearing {base_costume_id} with {adj.full_modifier}"


__all__ = ["CostumeAdjustment", "adjust", "merge_into_prompt", "ATMOSPHERE_TO_COSTUME"]
