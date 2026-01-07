from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .api_models import ToolCategory, ToolInfo


@dataclass(frozen=True)
class Tool:
    tool_id: str
    name: str
    category: ToolCategory
    version: str
    runner: Callable[[str, str, dict], None]  # (job_id, upload_id, params) -> None


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    TOOLS[tool.tool_id] = tool


def list_tools() -> list[ToolInfo]:
    return [
        ToolInfo(tool_id=t.tool_id, name=t.name, category=t.category, version=t.version)
        for t in sorted(TOOLS.values(), key=lambda x: x.tool_id)
    ]
