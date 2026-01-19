# backend/app/api/schemas/tools.py
"""
Tools API schemas.

Tools are runnable capabilities exposed by the backend (e.g., ignition.project.explorer).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """Describes a runnable tool."""

    tool_id: str = Field(alias="toolId")
    name: str
    description: str

    model_config = {"populate_by_name": True}


class ToolsList(BaseModel):
    """Response payload listing all available tools."""

    tools: list[ToolInfo]
