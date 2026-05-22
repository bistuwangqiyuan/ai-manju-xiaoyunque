"""Zip exporter for a finished batch (requirement doc §12 批量结果导出)."""
from __future__ import annotations

import json
import pathlib
import zipfile
from typing import Iterable


def export_batch_zip(
    batch_id: int,
    items: Iterable[dict],
    zip_path: str | pathlib.Path,
    *,
    manifest_extra: dict | None = None,
) -> str:
    """Write a single zip containing every output + a manifest.json."""
    zip_path = pathlib.Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    items_list = list(items)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in items_list:
            out = pathlib.Path(it["final_output"])
            if out.exists():
                zf.write(out, arcname=f"items/item_{it['item_id']:04d}{out.suffix or '.png'}")
        manifest = {
            "batch_id": batch_id,
            "items": items_list,
            "extra": manifest_extra or {},
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return str(zip_path)


__all__ = ["export_batch_zip"]
