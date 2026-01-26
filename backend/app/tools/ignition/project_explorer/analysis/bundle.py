"""
High-level orchestration for project analysis.

This is the entrypoint that turns:
- ZipFile + ProjectExport (parser output)
into:
- GraphBundle + ArtifactToWrite list
"""

from __future__ import annotations

import zipfile
from typing import Any

from app.core.time import utcnow_iso
from app.tools.ignition.project_explorer.models import (
    Graph,
    GraphBundle,
    GraphEdge,
    GraphNode,
)
from app.tools.ignition.project_explorer.parser import ProjectExport

from .artifacts import ArtifactToWrite, emit_resource_source_artifacts
from .echarts import emit_echarts_artifacts
from .edges import discover_edges_for_resource
from .metrics import compute_stats
from .nodes import build_nodes
from .profile import normalize_profile
from .tree import build_tree


def build_graph_bundle(
    *,
    zip_file: zipfile.ZipFile,
    export: ProjectExport,
    profile: dict[str, Any] | None,
) -> tuple[GraphBundle, list[ArtifactToWrite]]:
    """
    Build GraphBundle and per-node artifacts.

    Args:
        zip_file: Open ZipFile for reading file bodies.
        export: Parsed project export model (parser output).
        profile: Optional UI profile dict used to filter graph_ui.

    Returns:
        (GraphBundle, artifacts_to_write)
    """
    eff_profile = normalize_profile(profile or {})
    generated_at = utcnow_iso()

    node_result = build_nodes(resources=export.resources)
    nodes = node_result.nodes
    path_index = node_result.path_index

    artifacts: list[ArtifactToWrite] = []

    # Emit per-node source artifacts
    for res in export.resources:
        nid = nodes_for_resource(nodes, res)
        artifacts.extend(emit_resource_source_artifacts(zip_file, res, nid))

    # Build edges (may create derived nodes via resolver)
    edges: list[GraphEdge] = []
    for res in export.resources:
        nid = nodes_for_resource(nodes, res)
        src_node = nodes.get(nid)
        if not src_node:
            continue

        edges.extend(
            discover_edges_for_resource(
                zip_file=zip_file,
                res=res,
                src_node=src_node,
                nodes_by_norm_path=path_index,
                nodes=nodes,
            )
        )

    graph_full = Graph(nodes=list(nodes.values()), edges=edges)
    tree = build_tree(project_title=export.project.title or "Project", nodes=nodes)

    graph_ui = filter_graph_for_ui(graph_full, eff_profile)

    stats = compute_stats(export=export, graph_full=graph_full, graph_ui=graph_ui)

    bundle = GraphBundle(
        tool_id="ignition.project.explorer",
        generated_at=generated_at,
        project={
            "title": export.project.title,
            "description": export.project.description,
            "parent": export.project.parent,
            "raw_project_json": export.project.raw,
        },
        profile=eff_profile,
        stats=stats,
        graph_full=graph_full,
        graph_ui=graph_ui,
        tree=tree,
    )
    artifacts.extend(emit_echarts_artifacts(bundle))

    return bundle, artifacts


def nodes_for_resource(nodes: dict[str, GraphNode], res: Any) -> str:
    """
    Retrieve the node_id for a resource.

    We use the node ID stored in GraphNode metadata (resource_json_path/path/type)
    by re-deriving it the same way nodes.py did. This avoids the analysis layer
    depending on parser internals beyond Resource fields.
    """
    # nodes.py uses stable node ids and stored everything in nodes already,
    # but we need a lookup. We do it by matching live nodes by type+path.
    # This is O(N) but N is small enough for now, and keeps coupling low.
    for nid, n in nodes.items():
        if n.status == "live" and n.type == res.type_key and (n.path or "") == (res.path or ""):
            return nid

    # Should not happen; fallback to first live node with matching resource_json_path if available.
    rjp = getattr(res, "resource_json_path", None)
    if rjp:
        for nid, n in nodes.items():
            if n.status == "live" and n.metadata.get("resource_json_path") == rjp:
                return nid

    # Last resort: return a deterministic-but-non-ideal id by stable hash
    # (keeps output consistent even if parser output is malformed).
    from app.tools.ignition.project_explorer.util import (
        normalize_ignition_path,
        stable_uuid5,
    )

    return stable_uuid5(
        "node-fallback", res.type_key, normalize_ignition_path(res.path or res.type_key)
    )


def filter_graph_for_ui(graph: Graph, profile: dict[str, Any]) -> Graph:
    """
    Filter graph for default UI loading.

    Policy:
    - include live nodes of allowed types
    - include edges whose source is included
    - include the target node for every included edge (live or derived/missing),
      to keep the resulting graph structurally valid (no dangling edges)
    """
    ui_types: list[str] = profile.get("ui_types", [])
    allowed_nodes: dict[str, GraphNode] = {}
    node_by_id = {n.id: n for n in graph.nodes}

    # Keep live nodes of allowed types
    for n in graph.nodes:
        if n.status == "live" and n.type in ui_types:
            allowed_nodes[n.id] = n

    allowed_edges: list[GraphEdge] = []
    for e in graph.edges:
        if e.source not in allowed_nodes:
            continue

        allowed_edges.append(e)

        # Always include target node so edges are renderable
        tgt = node_by_id.get(e.target)
        if tgt:
            allowed_nodes[tgt.id] = tgt

    return Graph(nodes=list(allowed_nodes.values()), edges=allowed_edges)
