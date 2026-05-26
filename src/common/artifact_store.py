"""Content-addressed artifact store with version snapshots.

Used by the v2 orchestrator and batch transcribe subsystem to:

- Persist per-step / per-shot artifacts under a stable on-disk layout.
- Snapshot a job's full output tree as a version (rollback / compare / trace).
- Optionally mirror critical artifacts to S3-compatible storage (TOS / OSS / R2).

The store is intentionally filesystem-first so it works in mock mode without
any cloud configuration. When ``S3_BUCKET`` + ``S3_ACCESS_KEY`` env vars are
present we additionally upload artifacts via boto3 (lazy import).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

_log = logging.getLogger(__name__)


@dataclass
class ArtifactRef:
    """Pointer to a stored artifact."""

    key: str
    local_path: str
    sha256: str
    size_bytes: int
    remote_url: str | None = None
    mime: str = "application/octet-stream"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionSnapshot:
    """A frozen view of a job's artifact tree at one point in time."""

    version_no: int
    created_at: str
    notes: str = ""
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)
    scores: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


class ArtifactStore:
    """Per-job artifact + version store."""

    def __init__(self, root: str | pathlib.Path, *, enable_s3: bool | None = None):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.versions_dir = self.root / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if enable_s3 is None:
            enable_s3 = bool(os.environ.get("S3_BUCKET") and os.environ.get("S3_ACCESS_KEY"))
        self.enable_s3 = enable_s3

    # ------------------------------------------------------------------
    # Put / get
    # ------------------------------------------------------------------

    def put(
        self,
        key: str,
        src: str | pathlib.Path | bytes,
        *,
        mime: str = "application/octet-stream",
        meta: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        """Store one artifact under ``key`` and return its reference."""

        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(src, (bytes, bytearray)):
            target.write_bytes(src)
        else:
            src_path = pathlib.Path(src)
            if not src_path.exists():
                raise FileNotFoundError(src_path)
            if src_path.resolve() != target.resolve():
                shutil.copy2(src_path, target)
        payload = target.read_bytes()
        sha = hashlib.sha256(payload).hexdigest()
        ref = ArtifactRef(
            key=key,
            local_path=str(target.resolve()),
            sha256=sha,
            size_bytes=len(payload),
            mime=mime,
            meta=meta or {},
        )
        if self.enable_s3:
            try:
                ref.remote_url = self._mirror_s3(key, target)
            except Exception as e:  # pragma: no cover
                _log.warning("S3 mirror failed for %s: %s", key, e)
        return ref

    def get(self, key: str) -> pathlib.Path:
        target = self.root / key
        if not target.exists():
            raise FileNotFoundError(target)
        return target

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def list_keys(self, prefix: str = "") -> list[str]:
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return []
        return sorted(
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in base.rglob("*")
            if p.is_file() and "versions" not in p.parts[len(self.root.parts):]
        )

    # ------------------------------------------------------------------
    # Versions / snapshots
    # ------------------------------------------------------------------

    def snapshot(
        self,
        version_no: int,
        *,
        artifacts: dict[str, ArtifactRef] | Iterable[ArtifactRef] | None = None,
        scores: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        notes: str = "",
        copy_files: bool = True,
    ) -> VersionSnapshot:
        """Freeze a snapshot of ``artifacts`` (or every key under root)."""

        if artifacts is None:
            artifacts = {}
            for key in self.list_keys():
                p = self.root / key
                payload = p.read_bytes()
                sha = hashlib.sha256(payload).hexdigest()
                artifacts[key] = ArtifactRef(
                    key=key,
                    local_path=str(p.resolve()),
                    sha256=sha,
                    size_bytes=len(payload),
                )
        elif not isinstance(artifacts, dict):
            artifacts = {a.key: a for a in artifacts}

        snap = VersionSnapshot(
            version_no=version_no,
            created_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            artifacts=artifacts,
            scores=scores or {},
            params=params or {},
        )
        vdir = self.versions_dir / f"v{version_no:04d}"
        vdir.mkdir(parents=True, exist_ok=True)

        if copy_files:
            for ref in artifacts.values():
                dst = vdir / ref.key
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(ref.local_path, dst)
                except FileNotFoundError:
                    continue

        manifest = vdir / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "version_no": snap.version_no,
                    "created_at": snap.created_at,
                    "notes": snap.notes,
                    "scores": snap.scores,
                    "params": snap.params,
                    "artifacts": {k: asdict(v) for k, v in artifacts.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _log.info("snapshot v%d → %s (%d artifacts)", version_no, vdir, len(artifacts))
        return snap

    def load_snapshot(self, version_no: int) -> VersionSnapshot:
        vdir = self.versions_dir / f"v{version_no:04d}"
        manifest = vdir / "manifest.json"
        if not manifest.exists():
            raise FileNotFoundError(manifest)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        arts = {
            k: ArtifactRef(**v) for k, v in data.get("artifacts", {}).items()
        }
        return VersionSnapshot(
            version_no=data["version_no"],
            created_at=data["created_at"],
            notes=data.get("notes", ""),
            artifacts=arts,
            scores=data.get("scores", {}),
            params=data.get("params", {}),
        )

    def list_versions(self) -> list[int]:
        if not self.versions_dir.exists():
            return []
        out: list[int] = []
        for p in self.versions_dir.iterdir():
            if p.is_dir() and p.name.startswith("v"):
                try:
                    out.append(int(p.name[1:]))
                except ValueError:
                    continue
        return sorted(out)

    def rollback(self, version_no: int) -> int:
        """Copy artifacts from version ``version_no`` back over the live root.

        Returns the count of restored files.
        """
        snap = self.load_snapshot(version_no)
        vdir = self.versions_dir / f"v{version_no:04d}"
        restored = 0
        for key in snap.artifacts.keys():
            src = vdir / key
            dst = self.root / key
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                restored += 1
        _log.info("rolled back to v%d, restored %d files", version_no, restored)
        return restored

    def diff(self, va: int, vb: int) -> dict[str, dict[str, str]]:
        a = self.load_snapshot(va)
        b = self.load_snapshot(vb)
        keys = set(a.artifacts) | set(b.artifacts)
        out: dict[str, dict[str, str]] = {}
        for k in sorted(keys):
            ar = a.artifacts.get(k)
            br = b.artifacts.get(k)
            if ar is None:
                out[k] = {"status": "added", "to": br.sha256 if br else ""}
            elif br is None:
                out[k] = {"status": "removed", "from": ar.sha256}
            elif ar.sha256 != br.sha256:
                out[k] = {
                    "status": "changed",
                    "from": ar.sha256,
                    "to": br.sha256,
                }
            else:
                out[k] = {"status": "same", "sha256": ar.sha256}
        return out

    # ------------------------------------------------------------------
    # S3 mirror
    # ------------------------------------------------------------------

    def _mirror_s3(self, key: str, src: pathlib.Path) -> str | None:
        try:
            import boto3  # type: ignore
        except ImportError:
            return None
        bucket = os.environ["S3_BUCKET"]
        endpoint = os.environ.get("S3_ENDPOINT") or None
        region = os.environ.get("S3_REGION", "auto")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        s3_key = f"artifacts/{self.root.name}/{key}"
        client.upload_file(str(src), bucket, s3_key)
        public_base = os.environ.get("S3_PUBLIC_BASE_URL", "").rstrip("/")
        if public_base:
            return f"{public_base}/{s3_key}"
        return f"s3://{bucket}/{s3_key}"


    # ------------------------------------------------------------------
    # V10 §2.1 — tree-path naming convention
    # ------------------------------------------------------------------

    def tree_key(
        self,
        *,
        kind: str,                     # "script" | "asset" | "shot" | "ep" | "report" | "log"
        episode: int | None = None,
        shot: int | None = None,
        version: int | None = None,
        filename: str = "",
        subdir: str = "",
    ) -> str:
        """Generate the canonical tree path for an artifact.

        Format examples (lossless, sortable, predictable)::

            script/ep01.txt
            script/ep01_v2.txt
            asset/character/protagonist_front.png
            ep01/shot003_v2.mp4
            ep01/shot003_v2.scores.json
            report/scores_7d.csv
        """
        parts: list[str] = []
        if kind == "ep":
            ep = f"ep{episode:02d}" if episode is not None else "ep00"
            parts.append(ep)
            if shot is not None:
                stub = f"shot{shot:03d}"
                if version and version > 1:
                    stub += f"_v{version}"
                if filename:
                    stub += "." + filename.lstrip(".")
                parts.append(stub)
            elif filename:
                parts.append(filename)
        elif kind in ("script", "asset", "report", "log"):
            parts.append(kind)
            if subdir:
                parts.append(subdir)
            base = filename
            if episode is not None and not filename.startswith("ep"):
                base = f"ep{episode:02d}_{base}" if base else f"ep{episode:02d}.txt"
            if version and version > 1 and "_v" not in base:
                stem, _, ext = base.rpartition(".")
                base = f"{stem}_v{version}.{ext}" if stem else f"{base}_v{version}"
            parts.append(base)
        elif kind == "shot":
            ep = f"ep{episode:02d}" if episode is not None else "ep00"
            stub = f"shot{shot:03d}" if shot is not None else "shot000"
            if version and version > 1:
                stub += f"_v{version}"
            if filename:
                stub += "." + filename.lstrip(".")
            parts.extend([ep, stub])
        else:
            parts.append(filename or "misc.bin")
        return "/".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # V10 §2.2 — full-project bundle export (.zip)
    # ------------------------------------------------------------------

    def export_project_bundle(
        self,
        *,
        dst: str | pathlib.Path,
        include_versions: bool = True,
        manifest: dict[str, Any] | None = None,
    ) -> pathlib.Path:
        """Pack the entire job tree into a single ``.zip`` for download."""
        import zipfile

        dst_p = pathlib.Path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        files: list[pathlib.Path] = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            if not include_versions and "versions" in p.relative_to(self.root).parts:
                continue
            files.append(p)

        manifest_payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "n_files": len(files),
            "include_versions": include_versions,
            "extra": manifest or {},
            "files": [
                {
                    "path": str(p.relative_to(self.root)).replace("\\", "/"),
                    "size": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16],
                }
                for p in files
            ],
        }
        with zipfile.ZipFile(dst_p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bundle_manifest.json",
                        json.dumps(manifest_payload, ensure_ascii=False, indent=2))
            for p in files:
                rel = str(p.relative_to(self.root)).replace("\\", "/")
                zf.write(p, arcname=rel)
        _log.info("exported project bundle: %s (%d files, %d B)",
                  dst_p, len(files), dst_p.stat().st_size)
        return dst_p


__all__ = ["ArtifactStore", "ArtifactRef", "VersionSnapshot"]
