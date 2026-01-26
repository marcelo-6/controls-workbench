"""
Metrics and summary stats for the project explorer UI.
"""

from __future__ import annotations

from typing import Any

from app.tools.ignition.project_explorer.models import Graph, GraphNode
from app.tools.ignition.project_explorer.parser import ProjectExport


def compute_stats(*, export: ProjectExport, graph_full: Graph, graph_ui: Graph) -> dict[str, Any]:
    """
    Compute lightweight stats for the summary UI.

    Keep this fast and deterministic. Heavy analysis can be emitted as separate artifacts later.
    """

    def _count_by_type(nodes: list[GraphNode]) -> dict[str, int]:
        out: dict[str, int] = {}
        for n in nodes:
            out[n.type] = out.get(n.type, 0) + 1
        return out

    return {
        "project_title": export.project.title,
        "parent_project": export.project.parent,
        "resources_count": len(export.resources),
        "nodes_full": len(graph_full.nodes),
        "edges_full": len(graph_full.edges),
        "nodes_ui": len(graph_ui.nodes),
        "edges_ui": len(graph_ui.edges),
        "types_full": _count_by_type(graph_full.nodes),
        "types_ui": _count_by_type(graph_ui.nodes),
        "sections_present": sorted({r.section for r in export.resources}),
    }
