# backend/app/tools/ignition/project_explorer/indexing.py
"""
Ignition Project Explorer indexing and graph construction.

This module converts a parsed ProjectExport into:
- GraphBundle (graph_full + graph_ui + tree + summary stats)
- Derived nodes for missing and ambiguous references
- Edges with confidence scoring and evidence strings

The design intentionally separates:
- parsing/discovery (parser.py)
- graph/model construction (this module)
- orchestration + artifact writing (engine.py)

v1 focuses on correctness and extensibility over perfect reference resolution.
Heuristics are kept explicit and confidence-scored so the frontend can convey
uncertainty without hiding useful information.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from typing import Any

from app.core.time import utcnow_iso

from .models import Graph, GraphBundle, GraphEdge, GraphNode, TreeNode
from .parser import ProjectExport, Resource
from .util import (
    ReferenceHit,
    best_effort_suffix_candidates,
    extract_references_from_text,
    extract_style_classes,
    normalize_ignition_path,
    stable_uuid5,
    try_parse_json,
)


@dataclass(frozen=True)
class ArtifactToWrite:
    """
    A tool-produced artifact to be persisted by the tool runner.

    Attributes:
        kind: Artifact kind (used by your download-by-kind endpoint).
        rel_path: Relative filesystem path within the job directory.
        content_type: MIME type.
        bytes_: Artifact payload bytes.
        meta: Optional JSON-safe metadata for DB indexing.
    """

    kind: str
    rel_path: str
    content_type: str
    bytes_: bytes
    meta: dict[str, Any] | None = None


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
        export: Parsed project export model.
        profile: Optional profile dict used to filter graph_ui.

    Returns:
        (GraphBundle, artifacts_to_write)
    """
    eff_profile = _normalize_profile(profile or {})
    generated_at = utcnow_iso()

    nodes: dict[str, GraphNode] = {}
    path_index: dict[str, list[str]] = {}  # normalized_path -> [node_id,...]
    artifacts: list[ArtifactToWrite] = []

    # 1) Create nodes for all discovered resources.
    for res in export.resources:
        node = _resource_to_node(res)
        nodes[node.id] = node

        if node.path:
            npath = normalize_ignition_path(node.path)
            if npath:
                path_index.setdefault(npath, []).append(node.id)

        # 2) Produce per-node source artifacts (view.json, scripts, sql, resource/config, thumbnail)
        artifacts.extend(_resource_source_artifacts(zip_file, res, node.id))

    # 3) Build edges by scanning view.json, scripts, config.json/sql for references.
    edges: list[GraphEdge] = []
    for res in export.resources:
        src_id = _resource_node_id(res)
        # Skip if node missing (shouldn't happen)
        if src_id not in nodes:
            continue

        edges.extend(
            _discover_edges_for_resource(
                zip_file=zip_file,
                res=res,
                src_node=nodes[src_id],
                nodes_by_norm_path=path_index,
                nodes=nodes,
                artifacts=artifacts,
            )
        )

    graph_full = Graph(nodes=list(nodes.values()), edges=edges)

    # 4) Build Designer-ordered tree
    tree = _build_tree(export, nodes)

    # 5) Filter graph_ui by profile while keeping referenced missing/ambiguous nodes
    graph_ui = _filter_graph_for_ui(graph_full, eff_profile)

    # 6) Stats / summary
    stats = _compute_stats(export=export, graph_full=graph_full, graph_ui=graph_ui)

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

    return bundle, artifacts


# -------------------------
# Node construction
# -------------------------


def _resource_node_id(res: Resource) -> str:
    return stable_uuid5("node", res.type_key, normalize_ignition_path(res.path))


def _resource_to_node(res: Resource) -> GraphNode:
    node_id = _resource_node_id(res)

    label = res.path.split("/")[-1] if res.path else res.type_key
    tags = [res.type_key, f"section:{res.section}"]

    meta: dict[str, Any] = {
        "binary_only": bool(res.binary_only),
        "section": res.section,
    }

    return GraphNode(
        id=node_id,
        label=label,
        type=res.type_key,
        path=res.path,
        status="live",
        tags=tags,
        description=res.section,
        tooltip=res.path,
        metadata=meta,
    )


# -------------------------
# Artifacts
# -------------------------


def _resource_source_artifacts(
    zip_file: zipfile.ZipFile, res: Resource, node_id: str
) -> list[ArtifactToWrite]:
    out: list[ArtifactToWrite] = []

    for rf in res.files:
        try:
            raw = zip_file.read(rf.zip_path)
        except Exception:
            continue

        # Map file kinds to payload kinds and content-types.
        if rf.kind == "thumbnail":
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:thumbnail",
                    rel_path=f"nodes/{node_id}/thumbnail.png",
                    content_type="image/png",
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "thumbnail"},
                )
            )
            continue

        if rf.kind == "view.json":
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:view.json",
                    rel_path=f"nodes/{node_id}/view.json",
                    content_type="application/json",
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "view.json"},
                )
            )
            continue

        if rf.kind == "script":
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:code.py",
                    rel_path=f"nodes/{node_id}/code.py",
                    content_type="text/x-python; charset=utf-8",
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "code.py"},
                )
            )
            continue

        if rf.kind == "sql":
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:query.sql",
                    rel_path=f"nodes/{node_id}/query.sql",
                    content_type="text/plain; charset=utf-8",
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": "query.sql"},
                )
            )
            continue

        if rf.kind in ("resource.json", "config.json"):
            out.append(
                ArtifactToWrite(
                    kind=f"node:{node_id}:{rf.kind}",
                    rel_path=f"nodes/{node_id}/{rf.kind}",
                    content_type="application/json",
                    bytes_=raw,
                    meta={"node_id": node_id, "payload": rf.kind},
                )
            )
            continue

        # Everything else: keep raw as octet-stream if you decide to store later.
        # (v1 intentionally conservative)

    return out


# -------------------------
# Edge discovery
# -------------------------


def _discover_edges_for_resource(
    *,
    zip_file: zipfile.ZipFile,
    res: Resource,
    src_node: GraphNode,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
    artifacts: list[ArtifactToWrite],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []

    # Look through known text-bearing files for refs.
    for rf in res.files:
        if rf.kind not in (
            "view.json",
            "script",
            "sql",
            "config.json",
            "resource.json",
        ):
            continue
        try:
            raw = zip_file.read(rf.zip_path)
        except Exception:
            continue

        text = _decode_text(raw)
        if not text:
            continue

        # Special-case: Perspective style classes in view.json
        if rf.kind == "view.json":
            js = try_parse_json(raw)
            if isinstance(js, dict):
                edges.extend(
                    _edges_from_perspective_view_json(
                        src_node_id=src_node.id,
                        view_json=js,
                        nodes_by_norm_path=nodes_by_norm_path,
                        nodes=nodes,
                    )
                )

        hits = extract_references_from_text(text)
        for hit in hits:
            edges.extend(
                _resolve_hit_to_edges(
                    src_node_id=src_node.id,
                    hit=hit,
                    nodes_by_norm_path=nodes_by_norm_path,
                    nodes=nodes,
                )
            )

    return edges


def _decode_text(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except Exception:
        try:
            return raw.decode("latin-1")
        except Exception:
            return None


def _edges_from_perspective_view_json(
    *,
    src_node_id: str,
    view_json: dict[str, Any],
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []

    # 1) style.classes references
    # Perspective stores "style": {"classes": "a/b c/d"}
    classes = _find_style_classes_in_json(view_json)
    for cls in classes:
        tgt = _resolve_path_reference(
            ref_kind="style_class",
            ref_value=cls,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="perspective.style_class",
        )
        edges.append(
            GraphEdge(
                id=stable_uuid5("edge", src_node_id, tgt, "uses_style_class", cls),
                source=src_node_id,
                target=tgt,
                type="uses_style_class",
                confidence=(
                    1.0
                    if nodes[tgt].status == "live"
                    else nodes[tgt].metadata.get("confidence", 0.5)
                ),
                evidence=f"style.classes: {cls}",
            )
        )

    # 2) direct embedded view path properties (best-effort)
    view_paths = _find_view_paths_in_json(view_json)
    for vp in view_paths:
        tgt = _resolve_path_reference(
            ref_kind="view",
            ref_value=vp,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="perspective.view",
        )
        edges.append(
            GraphEdge(
                id=stable_uuid5("edge", src_node_id, tgt, "navigates_to", vp),
                source=src_node_id,
                target=tgt,
                type="navigates_to",
                confidence=(
                    1.0
                    if nodes[tgt].status == "live"
                    else nodes[tgt].metadata.get("confidence", 0.5)
                ),
                evidence=f"view reference: {vp}",
            )
        )

    return edges


def _find_style_classes_in_json(obj: Any) -> list[str]:
    classes: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "style" and isinstance(v, dict):
                cv = v.get("classes")
                if isinstance(cv, str):
                    classes.extend(extract_style_classes(cv))
            else:
                classes.extend(_find_style_classes_in_json(v))
    elif isinstance(obj, list):
        for it in obj:
            classes.extend(_find_style_classes_in_json(it))
    return classes


def _find_view_paths_in_json(obj: Any) -> list[str]:
    """
    Find Perspective view path usages in parsed view.json structures.

    This intentionally targets common patterns:
    - {"props": {"path": "<View/Path>"}}
    - {"viewPath": "<View/Path>"}  (page-config style)
    """
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("path", "viewPath") and isinstance(v, str) and "/" in v:
                out.append(v)
            else:
                out.extend(_find_view_paths_in_json(v))
    elif isinstance(obj, list):
        for it in obj:
            out.extend(_find_view_paths_in_json(it))
    return out


def _resolve_hit_to_edges(
    *,
    src_node_id: str,
    hit: ReferenceHit,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    tgt = None
    edge_type = "references"
    expected_prefix = None

    if hit.kind == "view":
        edge_type = "references_view"
        expected_prefix = "perspective.view"
        tgt = _resolve_path_reference(
            "view",
            hit.raw,
            nodes_by_norm_path,
            nodes,
            expected_type_prefix=expected_prefix,
        )

    elif hit.kind == "named_query":
        edge_type = "calls_named_query"
        expected_prefix = "named_query"
        tgt = _resolve_path_reference(
            "named_query",
            hit.raw,
            nodes_by_norm_path,
            nodes,
            expected_type_prefix=expected_prefix,
        )

    elif hit.kind == "tag":
        # v1: tags are not real resources in the Designer export, so we produce missing/derived nodes only.
        edge_type = "references_tag"
        tgt = _missing_node(nodes, ref_kind="tag", ref_value=hit.raw, confidence=0.4)

    if not tgt:
        return []

    confidence = (
        1.0 if nodes[tgt].status == "live" else float(nodes[tgt].metadata.get("confidence", 0.5))
    )

    return [
        GraphEdge(
            id=stable_uuid5("edge", src_node_id, tgt, edge_type, hit.raw),
            source=src_node_id,
            target=tgt,
            type=edge_type,
            confidence=confidence,
            evidence=f"{hit.kind}: {hit.raw}",
        )
    ]


def _resolve_path_reference(
    ref_kind: str,
    ref_value: str,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
    *,
    expected_type_prefix: str | None,
) -> str:
    """
    Resolve a path-like reference to:
    - an existing node (exact/suffix match),
    - an ambiguous derived node (multiple candidates),
    - or a missing node.

    Returns:
        target node id
    """
    ref_norm = normalize_ignition_path(ref_value)
    if not ref_norm:
        return _missing_node(nodes, ref_kind=ref_kind, ref_value=ref_value, confidence=0.2)

    # 1) exact normalized path match
    exact_ids = nodes_by_norm_path.get(ref_norm, [])
    exact_ids = _filter_by_type_prefix(nodes, exact_ids, expected_type_prefix)
    if len(exact_ids) == 1:
        return exact_ids[0]
    if len(exact_ids) > 1:
        return _ambiguous_node(
            nodes,
            ref_kind=ref_kind,
            ref_value=ref_value,
            candidates=exact_ids,
            confidence=0.9,
        )

    # 2) suffix match (partial)
    all_paths = list(nodes_by_norm_path.keys())
    suffix_paths = best_effort_suffix_candidates(ref_norm, all_paths)
    suffix_ids: list[str] = []
    for sp in suffix_paths:
        suffix_ids.extend(nodes_by_norm_path.get(normalize_ignition_path(sp), []))
    suffix_ids = _filter_by_type_prefix(nodes, suffix_ids, expected_type_prefix)
    suffix_ids = list(dict.fromkeys(suffix_ids))  # stable unique
    if len(suffix_ids) == 1:
        # partial match
        nid = suffix_ids[0]
        nodes[nid].metadata.setdefault("confidence", 0.6)
        return nid
    if len(suffix_ids) > 1:
        return _ambiguous_node(
            nodes,
            ref_kind=ref_kind,
            ref_value=ref_value,
            candidates=suffix_ids,
            confidence=0.6,
        )

    # 3) missing
    return _missing_node(nodes, ref_kind=ref_kind, ref_value=ref_value, confidence=0.4)


def _filter_by_type_prefix(
    nodes: dict[str, GraphNode], ids: list[str], prefix: str | None
) -> list[str]:
    if not prefix:
        return ids
    return [i for i in ids if nodes.get(i) and nodes[i].type.startswith(prefix)]


def _missing_node(
    nodes: dict[str, GraphNode], *, ref_kind: str, ref_value: str, confidence: float
) -> str:
    nid = stable_uuid5("missing", ref_kind, normalize_ignition_path(ref_value) or ref_value)
    if nid not in nodes:
        nodes[nid] = GraphNode(
            id=nid,
            label=ref_value,
            type=f"missing.{ref_kind}",
            path=ref_value,
            status="missing",
            tags=["missing", f"ref:{ref_kind}"],
            tooltip=ref_value,
            metadata={
                "ref_kind": ref_kind,
                "ref_value": ref_value,
                "confidence": confidence,
            },
        )
    return nid


def _ambiguous_node(
    nodes: dict[str, GraphNode],
    *,
    ref_kind: str,
    ref_value: str,
    candidates: list[str],
    confidence: float,
) -> str:
    nid = stable_uuid5("ambiguous", ref_kind, normalize_ignition_path(ref_value) or ref_value)
    if nid not in nodes:
        nodes[nid] = GraphNode(
            id=nid,
            label=ref_value,
            type=f"derived.ambiguous_{ref_kind}",
            path=ref_value,
            status="derived",
            tags=["derived", "ambiguous", f"ref:{ref_kind}"],
            tooltip=f"Ambiguous {ref_kind} reference",
            metadata={
                "ref_kind": ref_kind,
                "ref_value": ref_value,
                "candidates": candidates,
                "confidence": confidence,
            },
        )
    return nid


# -------------------------
# Tree + UI filtering
# -------------------------

_DESIGNER_SECTION_ORDER = [
    "Alarm Notification Pipelines",
    "Sequential Function Charts (SFC)",
    "Properties",
    "Scripting",
    "Perspective",
    "Transaction Groups",
    "Vision",
    "Event Streams",
    "Named Queries",
    "Reports",
]


def _build_tree(export: ProjectExport, nodes: dict[str, GraphNode]) -> TreeNode:
    """
    Build a Designer-ordered tree containing only present sections.
    """
    root = TreeNode(id="root", label=export.project.title or "Project", kind="root", children=[])

    # bucket resources by section
    section_to_items: dict[str, list[GraphNode]] = {}
    for n in nodes.values():
        if n.status != "live":
            continue
        sec = str(n.metadata.get("section") or "Other")
        section_to_items.setdefault(sec, []).append(n)

    # order sections, but only those that exist
    ordered_sections = [s for s in _DESIGNER_SECTION_ORDER if s in section_to_items]
    # append any unknown sections at end
    for s in sorted(section_to_items.keys()):
        if s not in ordered_sections:
            ordered_sections.append(s)

    for sec in ordered_sections:
        sec_node = TreeNode(id=f"sec:{sec}", label=sec, kind="section", children=[])
        items = section_to_items.get(sec, [])
        items.sort(key=lambda x: normalize_ignition_path(x.path or x.label))

        for n in items:
            _tree_insert(sec_node, n)

        if sec_node.children:
            root.children.append(sec_node)

    return root


def _tree_insert(section_node: TreeNode, node: GraphNode) -> None:
    """
    Insert a resource node into the section tree based on its path.
    """
    path = normalize_ignition_path(node.path or "")
    parts = [p for p in path.split("/") if p]

    # Leaf label is the last segment; folders are the prefix segments.
    leaf_label = parts[-1] if parts else node.label
    folders = parts[:-1]

    cur = section_node
    # walk folders
    for f in folders:
        child = next((c for c in cur.children if c.kind == "folder" and c.label == f), None)
        if not child:
            child = TreeNode(
                id=stable_uuid5(
                    "tree-folder",
                    section_node.id,
                    "/".join(folders[: folders.index(f) + 1]),
                ),
                label=f,
                kind="folder",
            )
            cur.children.append(child)
        cur = child

    thumb_kind = f"node:{node.id}:thumbnail" if node.type == "perspective.view" else None
    leaf = TreeNode(
        id=f"node:{node.id}",
        label=leaf_label,
        kind="node",
        node_id=node.id,
        node_type=node.type,
        thumbnail_kind=thumb_kind,
    )
    cur.children.append(leaf)


def _normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize/validate profile settings used for graph_ui filtering.

    Supported keys:
        ui_types: list[str] - include these node types in graph_ui
    """
    ui_types = profile.get("ui_types")
    if not isinstance(ui_types, list) or not ui_types:
        ui_types = [
            "perspective.view",
            "script.python",
            "script.gateway_event",
            "named_query",
            "perspective.style_class",
            "perspective.page_config",
            "sfc",
            "event_stream",
            "alarm_pipeline",
            "report",
            "project_properties",
        ]
    return {"ui_types": list(ui_types)}


def _filter_graph_for_ui(graph: Graph, profile: dict[str, Any]) -> Graph:
    """
    Filter graph for UI default loading while preserving missing/derived nodes
    that are referenced by included nodes.
    """
    ui_types: list[str] = profile.get("ui_types", [])
    allowed_nodes: dict[str, GraphNode] = {}

    # keep live nodes of allowed types
    for n in graph.nodes:
        if n.status != "live":
            continue
        if n.type in ui_types:
            allowed_nodes[n.id] = n

    # keep edges that connect allowed nodes; also keep missing/derived targets
    allowed_edges: list[GraphEdge] = []
    node_by_id = {n.id: n for n in graph.nodes}
    for e in graph.edges:
        if e.source not in allowed_nodes:
            continue
        allowed_edges.append(e)
        tgt = node_by_id.get(e.target)
        if tgt and tgt.status != "live":
            allowed_nodes[tgt.id] = tgt

    # also keep any derived/ambiguous nodes already included by edges (handled above)
    return Graph(nodes=list(allowed_nodes.values()), edges=allowed_edges)


def _compute_stats(*, export: ProjectExport, graph_full: Graph, graph_ui: Graph) -> dict[str, Any]:
    """
    Compute lightweight stats for summary UI.
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
