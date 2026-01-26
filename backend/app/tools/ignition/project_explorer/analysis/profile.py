"""
Profile normalization for graph_ui filtering.

Profiles are meant to control *default* UI loading (not correctness).
"""

from __future__ import annotations

from typing import Any

from app.tools.ignition.project_explorer import constants as C


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize/validate profile settings used for graph_ui filtering.

    Supported keys:
        ui_types: list[str] - node types to include in graph_ui

    If missing/invalid, falls back to a reasonable default set derived from constants.
    """
    ui_types = profile.get("ui_types")
    if not isinstance(ui_types, list) or not ui_types:
        ui_types = [
            C.TYPE_PERSPECTIVE_VIEW,
            C.TYPE_SCRIPT_PYTHON,
            C.TYPE_SCRIPT_GATEWAY_EVENT,
            C.TYPE_NAMED_QUERY,
            C.TYPE_PERSPECTIVE_STYLE_CLASS,
            C.TYPE_PERSPECTIVE_PAGE_CONFIG,
            C.TYPE_SFC,
            C.TYPE_EVENT_STREAM,
            C.TYPE_ALARM_PIPELINE,
            C.TYPE_REPORT,
            C.TYPE_PROJECT_PROPERTIES,
        ]
    return {"ui_types": list(ui_types)}
