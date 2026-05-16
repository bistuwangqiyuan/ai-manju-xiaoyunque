"""Shell 2 — Character asset production + triple ID lock.

Five-piece set:
    Seedream 5.0 Lite (main 8 multi-view)
        + 即梦 4.6     (variant 6 pose/wardrobe)
        + InfiniteYou  (ID embedding injection)
        + PuLID        (multi-character lock for shared frames)
        + FLUX Kontext (edit fallback for wardrobe drift)
"""

from .build_asset import CharacterAssetBuilder, CharacterAsset
from .gen_seedream import SeedreamClient
from .gen_jimeng import JimengImageClient
from .id_lock_infiniteyou import InfiniteYouClient
from .multi_id_pulid import PuLIDClient
from .edit_flux_kontext import FluxKontextClient

__all__ = [
    "CharacterAssetBuilder",
    "CharacterAsset",
    "SeedreamClient",
    "JimengImageClient",
    "InfiniteYouClient",
    "PuLIDClient",
    "FluxKontextClient",
]
