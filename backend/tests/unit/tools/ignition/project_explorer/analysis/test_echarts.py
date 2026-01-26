"""
Unit tests for ECharts artifact builders.

These tests target:
- build_echarts_graph_payload()
- build_echarts_tree_payload()
- emit_echarts_artifacts()

Goals:
- deterministic output (stable sorting and stable JSON bytes)
- correct category ordering (SECTION_ORDER first, then unknown sections appended)
- correct node/link mapping and degree counts
- correct tree enrichment and child sorting
- robust JSON safety via _json_safe()
"""

from __future__ import annotations

import json
from typing import Any

from app.tools.ignition.project_explorer import constants as C
from app.tools.ignition.project_explorer.analysis.echarts import (
    build_echarts_graph_payload,
    build_echarts_tree_payload,
    emit_echarts_artifacts,
)
from app.tools.ignition.project_explorer.models import (
    Graph,
    GraphBundle,
    GraphEdge,
    GraphNode,
    TreeNode,
)


def _node(
    *,
    nid: str,
    label: str,
    type_: str,
    path: str,
    section: str,
    status: str = "live",
    metadata: dict[str, Any] | None = None,
) -> GraphNode:
    """
    Helper to construct a GraphNode with minimal required fields.

    Notes:
    - The models in this project are typically Pydantic models (or dataclasses).
      We only use fields already used by indexing code, plus defaults for others.
    """
    meta = dict(metadata or {})
    meta.setdefault("section", section)
    return GraphNode(
        id=nid,
        label=label,
        type=type_,
        path=path,
        status=status,
        tags=[type_, f"section:{section}"],
        tooltip=path,
        description=section,
        metadata=meta,
    )


def _edge(
    *,
    eid: str,
    src: str,
    tgt: str,
    type_: str,
    confidence: float = 1.0,
    evidence: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GraphEdge:
    """Helper to construct a GraphEdge with minimal required fields."""
    return GraphEdge(
        id=eid,
        source=src,
        target=tgt,
        type=type_,
        confidence=confidence,
        evidence=evidence,
        metadata=dict(metadata or {}),
    )


def _bundle(*, graph_full: Graph, graph_ui: Graph, tree: TreeNode) -> GraphBundle:
    """
    Helper to construct a GraphBundle for emit_echarts_artifacts().

    Only fields required by emit_echarts_artifacts are populated.
    """
    return GraphBundle(
        tool_id="ignition.project.explorer",
        generated_at="2026-01-25T12:00:00Z",
        project={
            "title": "Demo",
            "description": None,
            "parent": None,
            "raw_project_json": {},
        },
        profile={"ui_types": []},
        stats={},
        graph_full=graph_full,
        graph_ui=graph_ui,
        tree=tree,
    )


def test_build_echarts_graph_payload_orders_categories_by_section_order_then_unknown():
    """
    Ensure categories are built using constants.SECTION_ORDER first (if present),
    with any unknown/discovered sections appended in sorted order.
    """
    n1 = _node(
        nid="b",
        label="B",
        type_=C.TYPE_SCRIPT_PYTHON,
        path="x/y",
        section=C.SECTION_SCRIPTS,
    )
    n2 = _node(
        nid="a",
        label="A",
        type_=C.TYPE_PERSPECTIVE_VIEW,
        path="Exchange/Dash",
        section=C.SECTION_PERSPECTIVE,
    )
    n3 = _node(nid="c", label="C", type_="custom.type", path="zzz", section="My Custom Section")
    g = Graph(nodes=[n1, n2, n3], edges=[])

    payload = build_echarts_graph_payload(g)

    cats = [c["name"] for c in payload["categories"]]
    assert cats.index(C.SECTION_PERSPECTIVE) < cats.index(C.SECTION_SCRIPTS)
    assert "My Custom Section" in cats
    # Unknown sections should come after the known SECTION_ORDER ones.
    assert cats.index("My Custom Section") > cats.index(C.SECTION_SCRIPTS)


def test_build_echarts_graph_payload_is_deterministic_and_degree_is_correct():
    """
    Validate:
    - nodes are sorted by id
    - edges are sorted by id
    - degree counts are assigned to node.value
    - links map edge.type into 'value', and include evidence/confidence
    """
    n_a = _node(
        nid="a",
        label="A",
        type_=C.TYPE_PERSPECTIVE_VIEW,
        path="A/A",
        section=C.SECTION_PERSPECTIVE,
    )
    n_b = _node(
        nid="b",
        label="B",
        type_=C.TYPE_PERSPECTIVE_VIEW,
        path="B/B",
        section=C.SECTION_PERSPECTIVE,
    )
    n_c = _node(
        nid="c",
        label="C",
        type_=C.TYPE_SCRIPT_PYTHON,
        path="C/C",
        section=C.SECTION_SCRIPTS,
    )

    # Create edges intentionally out-of-order to test sorting.
    e2 = _edge(
        eid="e2",
        src="a",
        tgt="b",
        type_="navigates_to",
        confidence=0.9,
        evidence="view ref",
    )
    e1 = _edge(
        eid="e1",
        src="a",
        tgt="c",
        type_="references",
        confidence=0.8,
        evidence="script ref",
    )

    g = Graph(nodes=[n_c, n_b, n_a], edges=[e2, e1])

    p1 = build_echarts_graph_payload(g)
    p2 = build_echarts_graph_payload(g)

    # Determinism: same structure every call
    assert p1 == p2

    node_ids = [n["id"] for n in p1["nodes"]]
    link_sources = [link["source"] for link in p1["links"]]
    link_targets = [link["target"] for link in p1["links"]]

    assert node_ids == ["a", "b", "c"]
    # edges sorted by id => e1 then e2
    assert p1["links"][0]["value"] == "references"
    assert p1["links"][1]["value"] == "navigates_to"
    assert link_sources == ["a", "a"]
    assert link_targets == ["c", "b"]

    # Degree counts: a has 2 (outgoing), b has 1 (incoming), c has 1 (incoming)
    by_id = {n["id"]: n for n in p1["nodes"]}
    assert by_id["a"]["value"] == 2
    assert by_id["b"]["value"] == 1
    assert by_id["c"]["value"] == 1

    # Evidence and confidence should be passed through
    assert p1["links"][0]["evidence"] == "script ref"
    assert p1["links"][0]["confidence"] == 0.8
    assert p1["links"][1]["evidence"] == "view ref"
    assert p1["links"][1]["confidence"] == 0.9


def test_build_echarts_tree_payload_enriches_leaf_nodes_and_sorts_children():
    """
    Ensure TreeNode conversion:
    - sorts children deterministically by (kind, label, id)
    - enriches leaf nodes (kind='node') using nodes_by_id when available
    - carries thumbnail_kind through
    """
    live = _node(
        nid="n-live",
        label="Dash",
        type_=C.TYPE_PERSPECTIVE_VIEW,
        path="Exchange/Dash/Dash",
        section=C.SECTION_PERSPECTIVE,
        metadata={"section": C.SECTION_PERSPECTIVE, "weird": {"x": 1}},
    )

    nodes_by_id = {live.id: live}

    # Children intentionally unsorted
    leaf2 = TreeNode(
        id="node:n-live",
        label="Dash",
        kind="node",
        node_id="n-live",
        node_type=live.type,
        thumbnail_kind="node:n-live:thumbnail",
    )
    leaf1 = TreeNode(
        id="node:missing",
        label="AAA",
        kind="node",
        node_id="missing",
        node_type="missing.tag",
    )
    folder = TreeNode(id="folder:1", label="Folder", kind="folder", children=[leaf2, leaf1])

    root = TreeNode(id="root", label="Project", kind="root", children=[folder])

    payload = build_echarts_tree_payload(root, nodes_by_id=nodes_by_id)

    assert payload["name"] == "Project"
    assert payload["kind"] == "root"
    assert payload["children"][0]["name"] == "Folder"

    # Folder children should be sorted by (kind, label, id)
    children = payload["children"][0]["children"]
    assert [c["name"] for c in children] == ["AAA", "Dash"]

    # Enrichment for live node
    dash = children[1]
    assert dash["node_id"] == "n-live"
    assert dash["node_type"] == C.TYPE_PERSPECTIVE_VIEW
    assert dash["path"] == "Exchange/Dash/Dash"
    assert dash["thumbnail_kind"] == "node:n-live:thumbnail"
    assert isinstance(dash["meta"], dict)

    # Non-enriched leaf should still keep node_id/type from TreeNode
    aaa = children[0]
    assert aaa["node_id"] == "missing"
    assert aaa["node_type"] == "missing.tag"


def test_json_safe_falls_back_to_str_for_non_serializable_metadata():
    """
    Validate _json_safe() behavior indirectly through build_echarts_graph_payload():
    if node.metadata contains non-JSON types, payload should still serialize.
    """
    n = _node(
        nid="a",
        label="A",
        type_=C.TYPE_SCRIPT_PYTHON,
        path="x",
        section=C.SECTION_SCRIPTS,
        metadata={
            "section": C.SECTION_SCRIPTS,
            "bad": set([1, 2, 3]),
        },  # not JSON serializable
    )
    g = Graph(nodes=[n], edges=[])
    payload = build_echarts_graph_payload(g)

    # meta should be JSON-safe (string fallback)
    assert isinstance(payload["nodes"][0]["meta"], (dict, str))
    # Must be JSON dumpable
    json.dumps(payload)


def test_emit_echarts_artifacts_emits_three_json_artifacts_and_is_byte_deterministic():
    """
    Ensure emit_echarts_artifacts():
    - returns exactly three artifacts with expected kinds/paths/content types
    - artifact bytes are deterministic (same bundle => same bytes)
    - artifacts decode to expected payload shapes
    """
    n1 = _node(
        nid="a",
        label="A",
        type_=C.TYPE_PERSPECTIVE_VIEW,
        path="A/A",
        section=C.SECTION_PERSPECTIVE,
    )
    n2 = _node(
        nid="b",
        label="B",
        type_=C.TYPE_SCRIPT_PYTHON,
        path="B/B",
        section=C.SECTION_SCRIPTS,
    )
    e1 = _edge(eid="e1", src="a", tgt="b", type_="references", evidence="ref")

    graph_full = Graph(nodes=[n1, n2], edges=[e1])
    graph_ui = Graph(nodes=[n1], edges=[])  # UI filtered example

    tree = TreeNode(id="root", label="Demo", kind="root", children=[])

    bundle = _bundle(graph_full=graph_full, graph_ui=graph_ui, tree=tree)

    arts1 = emit_echarts_artifacts(bundle)
    arts2 = emit_echarts_artifacts(bundle)

    assert [a.kind for a in arts1] == [
        "echarts_graph_full",
        "echarts_graph_ui",
        "echarts_tree",
    ]
    assert [a.rel_path for a in arts1] == [
        "echarts/graph_full.json",
        "echarts/graph_ui.json",
        "echarts/tree.json",
    ]
    assert all(a.content_type == "application/json" for a in arts1)

    # Deterministic bytes (sorted keys, indent)
    assert [a.bytes_ for a in arts1] == [a.bytes_ for a in arts2]

    # Payload shape validation
    p_full = json.loads(arts1[0].bytes_.decode("utf-8"))
    assert set(p_full.keys()) == {"categories", "nodes", "links"}
    assert len(p_full["nodes"]) == 2
    assert len(p_full["links"]) == 1

    p_ui = json.loads(arts1[1].bytes_.decode("utf-8"))
    assert len(p_ui["nodes"]) == 1

    p_tree = json.loads(arts1[2].bytes_.decode("utf-8"))
    assert p_tree["name"] == "Demo"
    assert p_tree["kind"] == "root"
