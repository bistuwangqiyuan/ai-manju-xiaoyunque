"""Compliance gates: copyright, sensitive content, AIGC labeling, novelty,
广电备案 auto-fill."""
from .copyright_scan import scan_copyright
from .sensitive_words import scan_sensitive_text
from .copyright_novelty import novelty_check, NoveltyReport
from .filing_autogen import autofill, categorize, FilingSummary

__all__ = [
    "scan_copyright",
    "scan_sensitive_text",
    "novelty_check",
    "NoveltyReport",
    "autofill",
    "categorize",
    "FilingSummary",
]
