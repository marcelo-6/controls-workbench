"""
ECharts data builders for Ignition Project Explorer.

This module converts internal models into ECharts-friendly JSON payloads.

Artifacts produced (JSON):
- echarts_graph_full: ECharts 'graph' series input for the full graph
- echarts_graph_ui:   ECharts 'graph' series input for the UI-filtered graph
- echarts_tree:       ECharts 'tree' series input based on the Designer-like tree

Design goals:
- deterministic output (stable sorting) for reproducible artifacts/tests
- no hardcoded section names (uses shared constants + discovered sections)
- provide "data-only" payloads (frontend can build chart options as it prefers)
"""

from __future__ import annotations

import json
from typing import Any

from app.tools.ignition.project_explorer import constants as C
from app.tools.ignition.project_explorer.models import (
    Graph,
    GraphBundle,
    GraphNode,
    TreeNode,
)

from .artifacts import ArtifactToWrite


def emit_echarts_artifacts(bundle: GraphBundle) -> list[ArtifactToWrite]:
    """
    Build and emit ECharts artifacts derived from a GraphBundle.

    Args:
        bundle: GraphBundle returned by the analysis layer.

    Returns:
        list[ArtifactToWrite]: JSON artifacts to persist.
    """
    out: list[ArtifactToWrite] = []

    # Pre-index nodes for tree enrichment
    nodes_by_id = {n.id: n for n in bundle.graph_full.nodes}

    graph_full_payload = build_echarts_graph_payload(bundle.graph_full)
    graph_ui_payload = build_echarts_graph_payload(bundle.graph_ui)
    tree_payload = build_echarts_tree_payload(bundle.tree, nodes_by_id=nodes_by_id)

    out.append(
        _json_artifact(
            kind="echarts_graph_full",
            rel_path="echarts/graph_full.json",
            payload=graph_full_payload,
            meta={"scope": "full", "format": "echarts.graph"},
        )
    )
    out.append(
        _json_artifact(
            kind="echarts_graph_ui",
            rel_path="echarts/graph_ui.json",
            payload=graph_ui_payload,
            meta={"scope": "ui", "format": "echarts.graph"},
        )
    )
    out.append(
        _json_artifact(
            kind="echarts_tree",
            rel_path="echarts/tree.json",
            payload=tree_payload,
            meta={"format": "echarts.tree"},
        )
    )

    return out


def build_echarts_graph_payload(graph: Graph) -> dict[str, Any]:
    """
    Convert a Graph into an ECharts 'graph' data payload.

    Output structure aligns with ECharts graph series expectations:
        {
          "categories": [{"name": "Perspective"}, ...],
          "nodes": [{"id": "...", "name": "...", "category": 0, ...}, ...],
          "links": [{"source": "...", "target": "...", "value": "navigates_to", ...}, ...]
        }

    Notes:
    - Nodes are categorized by their Designer section (node.metadata["section"]).
    - Links preserve edge.type as 'value' and include evidence for tooltips.
    - Output lists are sorted for determinism.
    """
    nodes = list(graph.nodes)
    edges = list(graph.edges)

    # Deterministic ordering
    nodes.sort(key=lambda n: n.id)
    edges.sort(key=lambda e: e.id)

    # Build categories using SECTION_ORDER first, then discovered unknown sections.
    discovered_sections = sorted({str(n.metadata.get("section") or "Other") for n in nodes})
    ordered_sections = [s for s in C.SECTION_ORDER if s in discovered_sections]
    for s in discovered_sections:
        if s not in ordered_sections:
            ordered_sections.append(s)

    category_index = {name: idx for idx, name in enumerate(ordered_sections)}
    categories = [{"name": name} for name in ordered_sections]

    # Degree counts (useful for sizing/styling in UI; do not hardcode symbolSize here)
    degree: dict[str, int] = {n.id: 0 for n in nodes}
    for e in edges:
        if e.source in degree:
            degree[e.source] += 1
        if e.target in degree:
            degree[e.target] += 1

    echarts_nodes: list[dict[str, Any]] = []
    for n in nodes:
        sec = str(n.metadata.get("section") or "Other")
        echarts_nodes.append(
            {
                "id": n.id,
                "name": n.label or n.id,
                "category": category_index.get(sec, category_index.get("Other", 0)),
                "value": degree.get(n.id, 0),
                "type": n.type,
                "path": n.path,
                "status": n.status,
                "tags": list(n.tags or []),
                "tooltip": n.tooltip,
                "meta": _json_safe(n.metadata),
            }
        )

    echarts_links: list[dict[str, Any]] = []
    for e in edges:
        echarts_links.append(
            {
                "source": e.source,
                "target": e.target,
                "value": e.type,
                "confidence": getattr(e, "confidence", None),
                "evidence": getattr(e, "evidence", None),
                "meta": _json_safe(getattr(e, "metadata", None) or {}),
            }
        )

    return {
        "categories": categories,
        "nodes": echarts_nodes,
        "links": echarts_links,
    }


def build_echarts_tree_payload(
    root: TreeNode, *, nodes_by_id: dict[str, GraphNode]
) -> dict[str, Any]:
    """
    Convert a Designer-like TreeNode structure into an ECharts 'tree' data payload.

    ECharts tree series expects:
        { "name": "...", "children": [ ... ] }

    We enrich leaf nodes (kind="node") with GraphNode details so tooltips can show
    path/type/status without extra requests.
    """

    def convert(t: TreeNode) -> dict[str, Any]:
        base: dict[str, Any] = {
            "name": t.label,
            "id": t.id,
            "kind": t.kind,
        }

        # Section/folder nodes: recurse
        if t.children:
            # Deterministic ordering: section/folder tree is already deterministic from builder,
            # but we enforce stable output for fixtures/tests.
            children = list(t.children)
            children.sort(key=lambda c: (c.kind, c.label, c.id))
            base["children"] = [convert(c) for c in children]

        # Leaf node enrichment
        if t.kind == "node" and t.node_id:
            n = nodes_by_id.get(t.node_id)
            if n:
                base["node_id"] = n.id
                base["node_type"] = n.type
                base["path"] = n.path
                base["status"] = n.status
                base["tags"] = list(n.tags or [])
                base["meta"] = _json_safe(n.metadata)
            else:
                base["node_id"] = t.node_id
                base["node_type"] = t.node_type

            if t.thumbnail_kind:
                base["thumbnail_kind"] = t.thumbnail_kind

        return base

    # ECharts tree commonly wants a single root object (not an array) for "data": [root].
    # We keep it as a root object; your UI can wrap as needed.
    return convert(root)


def _json_artifact(
    *, kind: str, rel_path: str, payload: dict[str, Any], meta: dict[str, Any] | None
) -> ArtifactToWrite:
    """
    Build a deterministic JSON ArtifactToWrite (sorted keys, stable formatting).
    """
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    return ArtifactToWrite(
        kind=kind,
        rel_path=rel_path,
        content_type="application/json",
        bytes_=raw,
        meta=meta,
    )


def _json_safe(obj: Any) -> Any:
    """
    Best-effort conversion to JSON-safe types.

    This is intentionally conservative; it ensures artifacts never fail serialization
    because of stray non-JSON types in metadata.
    """
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)
