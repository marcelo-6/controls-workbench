# backend/app/tools/ignition/project_explorer/engine.py
"""
Ignition Project Explorer tool engine.

This module is the orchestration layer for the Ignition Project Explorer tool.
It is responsible for:

- Opening the uploaded project export ZIP
- Parsing resources via `parser.py`
- Building the GraphBundle contract via `indexing.py`
- Emitting events and writing artifacts through the provided ToolContext

The engine intentionally does NOT:
- import FastAPI
- directly persist to the database
- assume any specific job storage layout

All persistence occurs via ToolContext callbacks implemented by your tool runner
service (which can index artifacts in DB and write bytes to the filesystem).
"""

from __future__ import annotations

import zipfile
from typing import Any

from app.core.errors import BadRequestError

from .indexing import (
    build_graph_bundle,
)
from .parser import parse_project_export


class ToolContextProto:
    """
    Minimal ToolContext protocol used by this tool.

    Your actual ToolContext can be richer; the engine only relies on:
    - emit_event(level, message, kind?, payload?)
    - write_artifact(kind, rel_path, bytes, content_type, meta?)
    """

    def emit_event(
        self,
        *,
        level: str,
        message: str,
        kind: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:  # noqa: D401
        ...

    def write_artifact(
        self,
        *,
        kind: str,
        rel_path: str,
        content_type: str,
        bytes_: bytes,
        meta: dict[str, Any] | None = None,
    ) -> None: ...


def run(
    ctx: ToolContextProto,
    *,
    project_zip_path: str,
    params: dict[str, Any] | None = None,
) -> None:
    """
    Run the Ignition Project Explorer tool.

    Args:
        ctx: ToolContext implementation provided by the domain tool runner.
        project_zip_path: Filesystem path to the uploaded Designer project export ZIP.
        params: Optional tool parameters (may include a selected profile).

    Raises:
        BadRequestError: If the ZIP cannot be opened or parsed.
    """
    params = params or {}
    profile = params.get("profile") if isinstance(params.get("profile"), dict) else {}

    ctx.emit_event(level="info", message="Opening project export ZIP", kind="tool")

    try:
        with zipfile.ZipFile(project_zip_path, "r") as zf:
            export = parse_project_export(zf)

            ctx.emit_event(
                level="info",
                message=f"Discovered resources: {len(export.resources)}",
                kind="parse",
                payload={"resources": len(export.resources)},
            )

            bundle, artifacts = build_graph_bundle(zip_file=zf, export=export, profile=profile)

    except zipfile.BadZipFile as e:
        raise BadRequestError(code="bad_zip", detail=f"Invalid ZIP file: {e}") from e
    except Exception as e:
        raise BadRequestError(
            code="parse_failed", detail=f"Failed to parse project export: {e}"
        ) from e

    # Write primary artifacts (graphs + tree + summary)
    ctx.emit_event(level="info", message="Writing graph artifacts", kind="artifact")

    _write_json_artifact(
        ctx,
        kind="graph_full",
        rel_path="graph_full.json",
        obj=bundle.graph_full.model_dump(mode="json"),
    )
    _write_json_artifact(
        ctx,
        kind="graph_ui",
        rel_path="graph_ui.json",
        obj=bundle.graph_ui.model_dump(mode="json"),
    )
    _write_json_artifact(
        ctx, kind="tree", rel_path="tree.json", obj=bundle.tree.model_dump(mode="json")
    )
    _write_json_artifact(
        ctx,
        kind="summary",
        rel_path="summary.json",
        obj=bundle.model_dump(
            mode="json",
            include={"tool_id", "generated_at", "project", "profile", "stats"},
        ),
    )

    # Write per-node artifacts
    ctx.emit_event(
        level="info",
        message=f"Writing node payload artifacts: {len(artifacts)}",
        kind="artifact",
    )
    for a in artifacts:
        ctx.write_artifact(
            kind=a.kind,
            rel_path=a.rel_path,
            content_type=a.content_type,
            bytes_=a.bytes_,
            meta=a.meta,
        )

    ctx.emit_event(
        level="info",
        message="Ignition graph build complete",
        kind="tool",
        payload={
            "nodes_full": bundle.stats.get("nodes_full"),
            "edges_full": bundle.stats.get("edges_full"),
            "nodes_ui": bundle.stats.get("nodes_ui"),
            "edges_ui": bundle.stats.get("edges_ui"),
        },
    )


def _write_json_artifact(ctx: ToolContextProto, *, kind: str, rel_path: str, obj: Any) -> None:
    import json

    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx.write_artifact(
        kind=kind,
        rel_path=rel_path,
        content_type="application/json",
        bytes_=raw,
        meta={"kind": kind},
    )
