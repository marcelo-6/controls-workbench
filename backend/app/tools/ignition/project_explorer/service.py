# backend/app/tools/ignition/project_explorer/service.py
"""
Ignition Project Explorer tool runner entrypoint.

This module provides the callable used by the tools registry. It adapts from the
generic tool runner interface (ToolContext + inputs + params) into the Ignition
Project Explorer engine.

Expected integration pattern:
- Domain ToolsService resolves upload paths and constructs a ToolContext that can:
  - emit DB-backed events
  - write artifacts to filesystem + index them in DB
- Tools registry maps tool_id "ignition.graph" to this `run_tool(...)` function.
"""

from __future__ import annotations

from typing import Any

from .engine import run as run_engine


def run_tool(ctx: Any, *, project_zip_path: str, params: dict[str, Any] | None = None) -> None:
    """
    Registry-facing tool runner.

    Args:
        ctx: ToolContext implementation from the domain tool runner.
        project_zip_path: Path to the uploaded project ZIP (Designer export).
        params: Optional params_json decoded to dict.

    Returns:
        None
    """
    run_engine(ctx, project_zip_path=project_zip_path, params=params or {})
