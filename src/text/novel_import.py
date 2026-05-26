"""V10 §3.1 — Novel importer.

Accepts bytes from a multipart upload + a format hint, and returns
clean Unicode text ready for chapter splitting.  Supported formats:

    .txt   (UTF-8, GBK auto-detect fallback)
    .docx  (python-docx)
    .pdf   (pypdf)

Heavy parsers are optional imports so the API stays runnable when those
wheels aren't present.
"""
from __future__ import annotations

import io
import re
import pathlib
from dataclasses import dataclass


# Conservative Chinese chapter regexp tries common variants:
#   第1章   第一章   第 1 章   第一回   第 1 节   Chapter 1
# A heading MUST occupy its own line (≤ 40 chars total, no further content).
_CHAPTER_RE = re.compile(
    r"^[\t ]*(?:"
    r"第\s*[零〇一二三四五六七八九十百千两0-9]+\s*[章回节卷集][^\n]{0,30}"
    r"|chapter\s+\d+[^\n]{0,30}"
    r"|prologue|epilogue|序章|楔子|尾声"
    r")[\t ]*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ImportedNovel:
    text: str
    total_chars: int
    source_format: str
    detected_chapters: int
    encoding_used: str | None = None
    warnings: list[str] | None = None


def import_txt(data: bytes) -> ImportedNovel:
    enc_used: str | None = None
    text: str
    try:
        text = data.decode("utf-8")
        enc_used = "utf-8"
    except UnicodeDecodeError:
        try:
            text = data.decode("gbk")
            enc_used = "gbk"
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="ignore")
            enc_used = "utf-8/ignore"
    text = _clean(text)
    return ImportedNovel(
        text=text, total_chars=len(text), source_format="txt",
        detected_chapters=_count_chapters(text), encoding_used=enc_used,
    )


def import_docx(data: bytes) -> ImportedNovel:
    try:
        import docx  # python-docx
    except Exception as exc:
        raise RuntimeError("python-docx 未安装: pip install python-docx") from exc
    doc = docx.Document(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if (p.text or "").strip()]
    text = _clean("\n".join(paragraphs))
    return ImportedNovel(
        text=text, total_chars=len(text), source_format="docx",
        detected_chapters=_count_chapters(text),
    )


def import_pdf(data: bytes) -> ImportedNovel:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("pypdf 未安装: pip install pypdf") from exc
    reader = PdfReader(io.BytesIO(data))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    text = _clean("\n".join(chunks))
    return ImportedNovel(
        text=text, total_chars=len(text), source_format="pdf",
        detected_chapters=_count_chapters(text),
    )


def import_any(filename: str, data: bytes) -> ImportedNovel:
    ext = pathlib.Path(filename).suffix.lower().lstrip(".")
    if ext in ("txt", "md", "text"):
        return import_txt(data)
    if ext == "docx":
        return import_docx(data)
    if ext == "pdf":
        return import_pdf(data)
    raise ValueError(f"不支持的格式: .{ext}")


def split_into_chapters(text: str, *, target_chars: int = 3000) -> list[dict]:
    """Split clean text into chapters by detected headings.

    When no headings are found, fall back to size-based chunking around
    ``target_chars`` so downstream pipelines always see something useful.
    """
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        return _size_based_split(text, target_chars=target_chars)

    chapters: list[dict] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        title = m.group(0).strip()
        if not body:
            continue
        chapters.append({"index": i + 1, "title": title, "body": body, "chars": len(body)})
    # Drop empty preamble (rare)
    if not chapters:
        return _size_based_split(text, target_chars=target_chars)
    return chapters


def _size_based_split(text: str, *, target_chars: int) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= target_chars:
        return [{"index": 1, "title": "全文", "body": text, "chars": len(text)}]

    chapters: list[dict] = []
    pieces = text.split("\n\n")
    buf = []
    buf_len = 0
    idx = 1
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if buf_len + len(piece) > target_chars and buf:
            body = "\n\n".join(buf)
            chapters.append({"index": idx, "title": f"第{idx}章", "body": body, "chars": len(body)})
            idx += 1
            buf = [piece]
            buf_len = len(piece)
        else:
            buf.append(piece)
            buf_len += len(piece)
    if buf:
        body = "\n\n".join(buf)
        chapters.append({"index": idx, "title": f"第{idx}章", "body": body, "chars": len(body)})
    return chapters


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # strip BOM / zero-width
    text = text.replace("\ufeff", "").replace("\u200b", "")
    return text.strip()


def _count_chapters(text: str) -> int:
    return sum(1 for _ in _CHAPTER_RE.finditer(text))


__all__ = [
    "ImportedNovel",
    "import_txt",
    "import_docx",
    "import_pdf",
    "import_any",
    "split_into_chapters",
]
