"""Platform content policy word filter (Douyin/Kuaishou baseline)."""
from __future__ import annotations

import re
from dataclasses import dataclass


_SENSITIVE_PATTERNS = [
    r"血腥",
    r"裸体",
    r"色情",
    r"赌博",
    r"毒品",
    r"自杀教程",
    r"邪教",
    r"分裂国家",
]


@dataclass
class SensitiveReport:
    passed: bool
    hits: list[str]


def scan_sensitive_text(text: str) -> SensitiveReport:
    hits: list[str] = []
    for pat in _SENSITIVE_PATTERNS:
        if re.search(pat, text):
            hits.append(pat)
    return SensitiveReport(passed=len(hits) == 0, hits=hits)
