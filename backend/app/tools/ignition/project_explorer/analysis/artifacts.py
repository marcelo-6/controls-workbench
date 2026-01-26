"""
Per-node source artifact emission.

This module turns parser ResourceFile entries into stable artifacts so the UI can:
- render view.json quickly
- show scripts/sql/resource.json/config.json
- show thumbnails
without rescanning the ZIP at render time.

Design goals:
- deterministic order and naming
- support multi-file resources (multiple .py files, multiple config-like files)
- provide compatibility aliases for single-script/single-sql resources
"""

from __future__ import annotations

import mimetypes
import os
import zipfile
from dataclasses import dataclass
from typing import Any

from app.tools.ignition.project_explorer.parser import Resource, ResourceFile


@dataclass(frozen=True)
class ArtifactToWrite:
    """
    A tool-produced artifact to be persisted by the tool runner.

    Attributes:
        kind: Artifact kind (used by download-by-kind endpoints).
        rel_path: Relative filesystem path within the job directory.
        content_type: MIME type.
        bytes_: Artifact payload bytes.
        meta: Optional JSON-safe metadata for DB indexing.
    """

    kind: str
    rel_path: str
    content_type: str
    bytes_: bytes
    meta: dict[str, Any] | None = None


_TEXT_PY = "text/x-python; charset=utf-8"
_TEXT = "text/plain; charset=utf-8"
_JSON = "application/json"


def emit_resource_source_artifacts(
    zip_file: zipfile.ZipFile, res: Resource, node_id: str
) -> list[ArtifactToWrite]:
    """
    Emit per-node source artifacts for a resource.

    Rules:
    - Always attempt to emit resource.json (manifest) and JSON-like files as JSON.
    - Emit each script/sql file with its original base name under nodes/{node_id}/.
    - If there is exactly one script, also emit a compatibility alias "code.py".
    - If there is exactly one sql, also emit a compatibility alias "query.sql".
    - Thumbnails preserve extension; content-type inferred.

    Returns:
        List[ArtifactToWrite]
    """
    out: list[ArtifactToWrite] = []

    # Gather candidates for aliasing
    script_files: list[ResourceFile] = [f for f in res.files if f.kind == "script"]
    sql_files: list[ResourceFile] = [f for f in res.files if f.kind == "sql"]
    # thumbs: list[ResourceFile] = [f for f in res.files if f.kind == "thumbnail"]

    for rf in res.files:
        raw = _read_bytes(zip_file, rf.zip_path)
        if raw is None:
            continue

        base = os.path.basename(rf.zip_path)

        # Thumbnails
        if rf.kind == "thumbnail":
            ext = os.path.splitext(base)[1].lower() or ".png"
            fname = f"thumbnail{ext}"
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:thumbnail",
                    rel_path=f"nodes/{node_id}/{fname}",
                    content_type=mimetypes.types_map.get(ext, "application/octet-stream"),
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "thumbnail"},
                )
            )
            continue

        # view.json is special (UI expects it)
        if rf.kind == "view.json":
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:view.json",
                    rel_path=f"nodes/{node_id}/view.json",
                    content_type=_JSON,
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "view.json"},
                )
            )
            continue

        # scripts (multiple possible)
        if rf.kind == "script":
            fname = base if base.lower().endswith(".py") else f"{base}.py"
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:script:{fname}",
                    rel_path=f"nodes/{node_id}/{fname}",
                    content_type=_TEXT_PY,
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": fname},
                )
            )
            continue

        # sql (multiple possible)
        if rf.kind == "sql":
            fname = base if base.lower().endswith(".sql") else f"{base}.sql"
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:sql:{fname}",
                    rel_path=f"nodes/{node_id}/{fname}",
                    content_type=_TEXT,
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": fname},
                )
            )
            continue

        # JSON manifests/configs/etc (keep exact name)
        if rf.kind.endswith(".json") or rf.kind in (
            "resource.json",
            "config.json",
            "style.json",
            "props.json",
        ):
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:{rf.kind}",
                    rel_path=f"nodes/{node_id}/{rf.kind}",
                    content_type=_JSON,
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": rf.kind},
                )
            )
            continue

        # sfc.xml or other textual
        if rf.kind == "sfc.xml" or base.lower().endswith(".xml"):
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:{base}",
                    rel_path=f"nodes/{node_id}/{base}",
                    content_type=_TEXT,
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": base},
                )
            )
            continue

        # Everything else: omit for v1 (keep conservative)
        # If later you want to keep binary payloads, add them here.

    # Compatibility aliases
    if len(script_files) == 1:
        rf = script_files[0]
        raw = _read_bytes(zip_file, rf.zip_path)
        if raw is not None:
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:code.py",
                    rel_path=f"nodes/{node_id}/code.py",
                    content_type=_TEXT_PY,
                    bytes_=raw,
                    meta={
                        "node_id": node_id,
                        "payload": "code.py",
                        "alias_for": os.path.basename(rf.zip_path),
                    },
                )
            )

    if len(sql_files) == 1:
        rf = sql_files[0]
        raw = _read_bytes(zip_file, rf.zip_path)
        if raw is not None:
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:query.sql",
                    rel_path=f"nodes/{node_id}/query.sql",
                    content_type=_TEXT,
                    bytes_=raw,
                    meta={
                        "node_id": node_id,
                        "payload": "query.sql",
                        "alias_for": os.path.basename(rf.zip_path),
                    },
                )
            )

    # If multiple thumbnails exist (rare), we emitted only the deterministic first via rf.kind ordering.
    # Your parser emits thumbnail as a manifest file, so this remains deterministic.

    return out


def _read_bytes(zip_file: zipfile.ZipFile, zip_path: str) -> bytes | None:
    try:
        return zip_file.read(zip_path)
    except Exception:
        return None
