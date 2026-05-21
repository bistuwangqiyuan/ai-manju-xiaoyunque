"""Copyright / adaptation risk scan (87 版徐克独创元素黑名单)."""
from __future__ import annotations

import re
from dataclasses import dataclass


# 87 版《倩女幽魂》独创视觉/情节 — 必须回避（compliance/filing_template §2.4）
_XUKE_87_BLACKLIST = [
    r"长舌.*姥姥",
    r"树妖.*长舌",
    r"浴桶.*吻",
    r"浴缸.*吻",
    r"黑山老妖",
    r"投胎转世",
    r"张国荣.*造型",
    r"王祖贤.*浴",
]


@dataclass
class CopyrightReport:
    passed: bool
    hits: list[str]
    notes: list[str]


def scan_copyright(text: str) -> CopyrightReport:
    hits: list[str] = []
    for pat in _XUKE_87_BLACKLIST:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(pat)
    notes = []
    if hits:
        notes.append("检测到可能侵权 87 版独创元素，请改写后重试。")
    else:
        notes.append("公版《聊斋》改编路径：未命中 87 版黑名单。")
    return CopyrightReport(passed=len(hits) == 0, hits=hits, notes=notes)
