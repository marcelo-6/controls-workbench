# backend/app/domain/tools/registry.py
"""
Tools registry.

This module provides an in-process registry mapping tool identifiers to:
- metadata required by the UI (name/description)
- an executable runner callable

The registry is intentionally simple:
- No dynamic plugin loading in v0.1
- Tool runners are injected at startup/import time

Runners must be pure-ish and communicate through the ToolContext callbacks:
- emit_event(...) for DB-backed logs
- write_artifact(...) for FS write + DB indexing handled by ToolsService
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolSpec:
    """
    Public metadata describing an available tool.

    Attributes:
        tool_id: Stable identifier used in API calls (e.g., "ignition.graph").
        name: Human-friendly name for UI selection lists.
        description: Short description for the UI.
    """

    tool_id: str
    name: str
    description: str


class ToolContext(Protocol):
    """
    Runtime context exposed to tool runners.

    Tool runners must not write directly to SQLite; they should instead emit
    events and artifacts through these callbacks so the platform can standardize
    persistence and indexing.
    """

    job_id: str
    upload_id: str

    def emit_event(
        self,
        level: str,
        message: str,
        kind: str | None = None,
        payload: dict | None = None,
    ) -> None: ...
    def get_project_zip_path(self) -> str: ...
    def get_tags_json_path(self) -> str | None: ...
    def write_artifact(
        self,
        *,
        kind: str,
        rel_path: str,
        content_type: str,
        data: bytes,
        meta: dict | None = None,
    ) -> None: ...


ToolRunner = Callable[[ToolContext], None]


class ToolsRegistry:
    """
    In-memory registry of tools available to the application.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._runners: dict[str, ToolRunner] = {}

    def register(self, spec: ToolSpec, runner: ToolRunner) -> None:
        """
        Register a tool specification and its runner.

        Args:
            spec: Tool metadata for UI and validation.
            runner: Callable that executes tool logic using a ToolContext.

        Raises:
            ValueError: If a tool_id is already registered.
        """
        if spec.tool_id in self._specs:
            raise ValueError(f"Tool already registered: {spec.tool_id}")
        self._specs[spec.tool_id] = spec
        self._runners[spec.tool_id] = runner

    def get_spec(self, tool_id: str) -> ToolSpec | None:
        """
        Return tool metadata for a given tool_id.

        Args:
            tool_id: Tool identifier.

        Returns:
            ToolSpec | None: Tool spec if registered.
        """
        return self._specs.get(tool_id)

    def get_runner(self, tool_id: str) -> ToolRunner | None:
        """
        Return tool runner for a given tool_id.

        Args:
            tool_id: Tool identifier.

        Returns:
            ToolRunner | None: Runner callable if registered.
        """
        return self._runners.get(tool_id)

    def list_tools(self) -> list[ToolSpec]:
        """
        List all registered tools.

        Returns:
            list[ToolSpec]: Registered tool specs ordered by insertion.
        """
        return list(self._specs.values())


def build_tools_registry() -> ToolsRegistry:
    reg = ToolsRegistry()

    try:
        from app.tools.ignition.project_explorer.service import (
            run_tool as ignition_project_explorer_runner,
        )

        reg.register(
            spec=ToolSpec(
                tool_id="ignition.project.explorer",
                name="Ignition Project Explorer",
                description="Parse an Ignition Designer project export ZIP and build a dependency graph.",
            ),
            runner=ignition_project_explorer_runner(),
        )
    except Exception as exc:
        print(f"{str(exc)}")

    # reg.register(... ignition.graph ...)
    return reg
