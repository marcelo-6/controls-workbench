# backend/app/tools/ignition/project_explorer/engine.py
"""
Ignition Project Explorer tool engine.

Orchestrates:
- open ZIP
- parse export
- build GraphBundle + node payload artifacts
- emit events + write artifacts via ToolContext

This module is HTTP/DB independent. Persistence is delegated through ToolContext.
"""

from __future__ import annotations

import json
import zipfile
from typing import Any

from app.core.errors import BadRequestError
from app.domain.tools.registry import ToolContext

# from .indexing import build_graph_bundle
from .analysis import build_graph_bundle
from .parser import parse_project_export


def run(
    ctx: ToolContext,
    *,
    project_zip_path: str,
    tags_json_path: str | None = None,
    params: dict[str, Any] | None = None,
) -> None:
    """
    Run the Ignition Project Explorer tool.

    Args:
        ctx: Tool execution context (events + artifact writes).
        project_zip_path: Path to the uploaded Designer project export ZIP.
        tags_json_path: Optional path to a tags export JSON (future; ignored in v1).
        params: Optional tool parameters.

    Raises:
        BadRequestError: If the ZIP cannot be opened or parsed.
    """
    _ = tags_json_path  # v1: reserved for future
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

            bundle, node_artifacts = build_graph_bundle(
                zip_file=zf,
                export=export,
                profile=profile,
            )

    except zipfile.BadZipFile as e:
        raise BadRequestError(code="bad_zip", detail=f"Invalid ZIP file: {e}") from e
    except Exception as e:
        raise BadRequestError(
            code="parse_failed", detail=f"Failed to parse project export: {e}"
        ) from e

    # Top-level artifacts
    ctx.emit_event(level="info", message="Writing graph artifacts", kind="artifact")

    _write_json(
        ctx,
        kind="graph_full",
        rel_path="graph_full.json",
        obj=bundle.graph_full.model_dump(mode="json"),
    )
    _write_json(
        ctx,
        kind="graph_ui",
        rel_path="graph_ui.json",
        obj=bundle.graph_ui.model_dump(mode="json"),
    )
    _write_json(ctx, kind="tree", rel_path="tree.json", obj=bundle.tree.model_dump(mode="json"))
    _write_json(
        ctx,
        kind="summary",
        rel_path="summary.json",
        obj=bundle.model_dump(
            mode="json",
            include={"tool_id", "generated_at", "project", "profile", "stats"},
        ),
    )

    # Per-node payload artifacts (thumbnail, view.json, code.py, query.sql, resource.json, config.json)
    ctx.emit_event(
        level="info",
        message=f"Writing node payload artifacts: {len(node_artifacts)}",
        kind="artifact",
        payload={"count": len(node_artifacts)},
    )

    for a in node_artifacts:
        ctx.write_artifact(
            kind=a.kind,
            rel_path=a.rel_path,
            content_type=a.content_type,
            data=a.bytes_,
            meta=a.meta,
        )

    ctx.emit_event(
        level="info",
        message="Ignition project explorer complete",
        kind="tool",
        payload={
            "nodes_full": bundle.stats.get("nodes_full"),
            "edges_full": bundle.stats.get("edges_full"),
            "nodes_ui": bundle.stats.get("nodes_ui"),
            "edges_ui": bundle.stats.get("edges_ui"),
        },
    )


def _write_json(ctx: ToolContext, *, kind: str, rel_path: str, obj: Any) -> None:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx.write_artifact(
        kind=kind,
        rel_path=rel_path,
        content_type="application/json",
        data=raw,
        meta={"kind": kind},
    )
