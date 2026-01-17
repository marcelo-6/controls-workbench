# backend/app/api/routes/tools.py
"""
Tool registry routes.

These endpoints are used to populate the UI tool picker and to provide basic
metadata for available tools.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_tools_registry, require_auth
from app.api.schemas.tools import ToolInfo, ToolsList
from app.core.responses import APIResponse, ok
from app.domain.tools.registry import ToolsRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=APIResponse[ToolsList], dependencies=[Depends(require_auth)])
def list_tools(
    registry: ToolsRegistry = Depends(get_tools_registry),
) -> APIResponse[ToolsList]:
    """
    List all registered tools.

    Args:
        registry: Tools registry.

    Returns:
        APIResponse[ToolsList]: Tool list for UI display.
    """
    tools = [
        ToolInfo(toolId=t.tool_id, name=t.name, description=t.description)
        for t in registry.list_tools()
    ]
    return ok(ToolsList(tools=tools))
