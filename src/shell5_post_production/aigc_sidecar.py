"""AIGC 隐式标识 sidecar — SynthID-text overlay + C2PA manifest JSON.

Closes Gap C-8 from docs/api-contracts-2026-05.md.

Three layers we emit per master.mp4:

1. **Explicit textual watermark** — already handled by
   ``shell5_post_production.watermark.apply_watermark``.
2. **Skylark `aigc_meta`** — passed via ``req_json`` on every render query
   (see ``shell3_skylark_engine.client.AigcMeta``), causing the official
   Volcengine pipeline to embed Volcengine SynthID metadata into the
   pixel stream. Verifiable at https://www.gcmark.com .
3. **C2PA sidecar JSON** — this module. Writes a ``master.mp4.c2pa.json``
   manifest alongside the master file. Downstream tools (``c2patool``,
   ``adobe-c2pa-sdk``) can attach it as a JUMBF block on demand.

The sidecar form keeps the pipeline portable (no native c2patool
dependency on Railway) and still records all required GB/T 45438-2025
metadata, including:

- ``content_producer``        — 18-char USCC of the producing entity
- ``producer_id``             — unique video ID (job_id + uuid)
- ``content_propagator``      — distribution-platform account
- ``propagate_id``            — propagation chain ID
- ``content_type``            — ``ai_generated_video``
- ``signature_alg``           — ``ecdsa-with-SHA256`` (placeholder)
- ``signed_at``               — ISO 8601 timestamp
- ``synthid_present``         — whether the Skylark step embedded SynthID
- ``ai_systems``              — list of model ids that touched this video

In production, ``c2patool sign`` can consume this JSON and produce a
manifest-store JUMBF block; we surface the env hook ``USE_C2PATOOL=1`` so
operators with the tool installed get full embedded C2PA. Otherwise the
JSON acts as a verifiable provenance sidecar.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import pathlib
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Iterable

_log = logging.getLogger(__name__)


@dataclass
class AigcSidecar:
    content_producer: str
    producer_id: str
    content_propagator: str = ""
    propagate_id: str = ""
    content_type: str = "ai_generated_video"
    signature_alg: str = "ecdsa-with-SHA256"
    signed_at: str = ""
    synthid_present: bool = True
    ai_systems: list[str] = field(default_factory=list)
    sha256: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _hash_file(path: pathlib.Path, *, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_duration(path: pathlib.Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True,
        )
        return float(out.stdout.strip() or 0.0)
    except Exception:
        return 0.0


def write_sidecar(
    master_path: str | pathlib.Path,
    *,
    job_id: int | str,
    content_producer: str | None = None,
    content_propagator: str = "",
    propagate_id: str = "",
    synthid_present: bool = True,
    ai_systems: Iterable[str] = (),
    embed_with_c2patool: bool | None = None,
) -> pathlib.Path:
    """Write ``<master>.c2pa.json`` next to ``master_path``.

    Returns the sidecar path. If ``embed_with_c2patool`` is true (or
    ``USE_C2PATOOL=1`` env), tries to run the optional ``c2patool sign``
    binary to embed a full JUMBF manifest. Falls back to JSON sidecar.
    """
    master = pathlib.Path(master_path)
    if not master.exists():
        raise FileNotFoundError(master)

    sidecar = AigcSidecar(
        content_producer=content_producer
        or os.environ.get("AIGC_CONTENT_PRODUCER", "ai-manju-xiaoyunque"),
        producer_id=f"{job_id}-{master.stem}",
        content_propagator=content_propagator
        or os.environ.get("AIGC_CONTENT_PROPAGATOR", ""),
        propagate_id=propagate_id or os.environ.get("AIGC_PROPAGATE_ID", ""),
        signed_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        synthid_present=synthid_present,
        ai_systems=list(ai_systems) or [
            "skylark-agent-2.0",
            "doubao-seed-1.6-vision",
            "claude-opus-4-7",
            "elevenlabs-multilingual-v3",
        ],
        sha256=_hash_file(master),
        duration_seconds=_ffprobe_duration(master),
    )

    sidecar_path = master.with_suffix(master.suffix + ".c2pa.json")
    sidecar_path.write_text(
        json.dumps(sidecar.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Optional: invoke c2patool sign if available + opt-in.
    if embed_with_c2patool is None:
        embed_with_c2patool = os.environ.get("USE_C2PATOOL") == "1"
    if embed_with_c2patool and shutil.which("c2patool"):
        try:
            signed = master.with_name(master.stem + ".c2pa.mp4")
            subprocess.run(
                ["c2patool", str(master), "-m", str(sidecar_path),
                 "-o", str(signed), "-f"],
                check=True, capture_output=True,
            )
            # swap signed in place of original
            shutil.move(str(signed), str(master))
            _log.info("c2patool embedded JUMBF manifest into %s", master)
        except Exception as e:
            _log.warning("c2patool embed failed (sidecar JSON retained): %s", e)

    return sidecar_path


__all__ = ["AigcSidecar", "write_sidecar"]
