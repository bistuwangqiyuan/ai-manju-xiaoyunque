"""Compliance gates: copyright, sensitive content, AIGC labeling."""
from .copyright_scan import scan_copyright
from .sensitive_words import scan_sensitive_text

__all__ = ["scan_copyright", "scan_sensitive_text"]
