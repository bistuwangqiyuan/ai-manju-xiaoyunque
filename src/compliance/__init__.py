"""Compliance gates: copyright, sensitive content, AIGC labeling, novelty,
广电备案 auto-fill, pHash + simhash copyright fingerprint library, post-VLM
adult/blood reviewer (V10 §11.3)."""
from .copyright_scan import scan_copyright
from .sensitive_words import scan_sensitive_text
from .copyright_novelty import novelty_check, NoveltyReport
from .filing_autogen import autofill, categorize, FilingSummary
from .copyright_fp import (
    CopyrightRegistry,
    Record as CopyrightRecord,
    image_phash,
    text_simhash,
    get_registry,
)
from .post_vlm_review import review_image, review_clip, ReviewReport

__all__ = [
    "scan_copyright",
    "scan_sensitive_text",
    "novelty_check",
    "NoveltyReport",
    "autofill",
    "categorize",
    "FilingSummary",
    "CopyrightRegistry",
    "CopyrightRecord",
    "image_phash",
    "text_simhash",
    "get_registry",
    "review_image",
    "review_clip",
    "ReviewReport",
]
