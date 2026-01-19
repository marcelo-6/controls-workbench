# backend/app/tools/ignition/project_explorer/service.py
"""
Ignition Project Explorer tool runner entrypoint.

This module exports the registry-facing runner callable (`run_tool`) that conforms
to the platform ToolRunner contract: Callable[[ToolContext], None].

The runner adapts the platform ToolContext into the tool engine inputs by
retrieving uploaded artifact paths via ToolContext methods.
"""

from __future__ import annotations

from typing import Any

from app.domain.tools.registry import ToolContext

from .engine import run as run_engine


def run_tool(ctx: ToolContext) -> None:
    """
    Execute the Ignition Project Explorer tool.

    Args:
        ctx: Platform tool context. Provides access to the uploaded ZIP path and
            artifact/event callbacks.
    """
    project_zip_path = ctx.get_project_zip_path()
    tags_json_path = ctx.get_tags_json_path()

    # If later you add profile selection into ctx, you can pass it here.
    params: dict[str, Any] = {}

    run_engine(
        ctx,
        project_zip_path=project_zip_path,
        tags_json_path=tags_json_path,
        params=params,
    )
