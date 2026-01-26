"""
Node construction for the analysis layer.

Converts parser Resource objects into GraphNode objects and builds a path index
to support reference resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tools.ignition.project_explorer.models import GraphNode
from app.tools.ignition.project_explorer.util import normalize_ignition_path

from .ids import node_id


@dataclass(frozen=True)
class NodeBuildResult:
    """
    Output of node building.

    Attributes:
        nodes: Node map by node_id.
        path_index: Mapping normalized_path -> [node_id,...] for resolution.
    """

    nodes: dict[str, GraphNode]
    path_index: dict[str, list[str]]


def build_nodes(*, resources: list[Any]) -> NodeBuildResult:
    """
    Build GraphNode objects for all discovered resources.

    Args:
        resources: List[parser.Resource] objects.

    Returns:
        NodeBuildResult with:
          - nodes map by ID
          - path_index mapping normalized paths to node IDs
    """
    nodes: dict[str, GraphNode] = {}
    path_index: dict[str, list[str]] = {}

    for res in resources:
        nid = node_id(type_key=res.type_key, logical_path=res.path)

        label = (res.path.split("/")[-1] if res.path else res.type_key) or res.type_key
        tags = [res.type_key, f"section:{res.section}"]

        meta: dict[str, Any] = {
            "binary_only": bool(getattr(res, "binary_only", False)),
            "section": res.section,
            "files": [f.kind for f in res.files],
            "resource_json_path": getattr(res, "resource_json_path", None),
            "attributes": getattr(res, "attributes", None),
        }

        nodes[nid] = GraphNode(
            id=nid,
            label=label,
            type=res.type_key,
            path=res.path,
            status="live",
            tags=tags,
            description=res.section,
            tooltip=res.path,
            metadata=meta,
        )

        npath = normalize_ignition_path(res.path or "")
        if npath:
            path_index.setdefault(npath, []).append(nid)

    return NodeBuildResult(nodes=nodes, path_index=path_index)
