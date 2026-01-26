"""
Edge discovery for the analysis layer.

We discover edges by scanning text-bearing resource files for references.
We also special-case Perspective `view.json` parsing to detect:
- embedded view paths
- style class usage

All heuristics produce:
- explicit evidence strings
- confidence scores (live=1.0, derived/missing uses node metadata confidence)
"""

from __future__ import annotations

import zipfile
from typing import Any

from app.tools.ignition.project_explorer.models import GraphEdge, GraphNode
from app.tools.ignition.project_explorer.parser import Resource
from app.tools.ignition.project_explorer.util import (
    ReferenceHit,
    extract_references_from_text,
    extract_style_classes,
    try_parse_json,
)

from .ids import edge_id
from .resolver import missing_node, resolve_path_reference

_TEXT_KINDS = {
    "view.json",
    "script",
    "sql",
    "config.json",
    "resource.json",
    "style.json",
    "props.json",
    "stylesheet.css",
    "sfc.xml",
}


def discover_edges_for_resource(
    *,
    zip_file: zipfile.ZipFile,
    res: Resource,
    src_node: GraphNode,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    """
    Discover edges for a resource by scanning its files.

    Args:
        zip_file: Open zip.
        res: Resource from parser.
        src_node: Source node corresponding to the resource.
        nodes_by_norm_path: normalized path index.
        nodes: all nodes (mutable, because derived nodes may be created).

    Returns:
        list[GraphEdge]
    """
    edges: list[GraphEdge] = []

    for rf in res.files:
        if rf.kind not in _TEXT_KINDS:
            continue

        raw = _read_bytes(zip_file, rf.zip_path)
        if raw is None:
            continue

        text = _decode_text(raw)
        if not text:
            continue

        # Special: parse view.json for view + style class references
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

        # Generic text hit extraction (scripts/sql/resource/config)
        hits = extract_references_from_text(text)
        for hit in hits:
            edges.extend(
                _edges_from_reference_hit(
                    src_node_id=src_node.id,
                    hit=hit,
                    nodes_by_norm_path=nodes_by_norm_path,
                    nodes=nodes,
                )
            )

    return edges


def _edges_from_perspective_view_json(
    *,
    src_node_id: str,
    view_json: dict[str, Any],
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []

    # 1) style.classes references
    classes = _find_style_classes_in_json(view_json)
    for cls in classes:
        tgt = resolve_path_reference(
            ref_kind="style_class",
            ref_value=cls,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="perspective.style_class",
        )
        edges.append(
            _edge(
                src_id=src_node_id,
                tgt_id=tgt,
                edge_type="uses_style_class",
                evidence=f"style.classes: {cls}",
                nodes=nodes,
            )
        )

    # 2) embedded view path references (best-effort)
    view_paths = _find_view_paths_in_json(view_json)
    for vp in view_paths:
        tgt = resolve_path_reference(
            ref_kind="view",
            ref_value=vp,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="perspective.view",
        )
        edges.append(
            _edge(
                src_id=src_node_id,
                tgt_id=tgt,
                edge_type="navigates_to",
                evidence=f"view reference: {vp}",
                nodes=nodes,
            )
        )

    return edges


def _edges_from_reference_hit(
    *,
    src_node_id: str,
    hit: ReferenceHit,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    tgt: str | None = None
    edge_type = "references"

    if hit.kind == "view":
        edge_type = "references_view"
        tgt = resolve_path_reference(
            ref_kind="view",
            ref_value=hit.raw,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="perspective.view",
        )

    elif hit.kind == "named_query":
        edge_type = "calls_named_query"
        tgt = resolve_path_reference(
            ref_kind="named_query",
            ref_value=hit.raw,
            nodes_by_norm_path=nodes_by_norm_path,
            nodes=nodes,
            expected_type_prefix="named_query",
        )

    elif hit.kind == "tag":
        # Tags are not resources in project exports; always create missing nodes for now.
        edge_type = "references_tag"
        tgt = missing_node(nodes, ref_kind="tag", ref_value=hit.raw, confidence=0.4)

    if not tgt:
        return []

    return [
        _edge(
            src_id=src_node_id,
            tgt_id=tgt,
            edge_type=edge_type,
            evidence=f"{hit.kind}: {hit.raw}",
            nodes=nodes,
        )
    ]


def _edge(
    *,
    src_id: str,
    tgt_id: str,
    edge_type: str,
    evidence: str,
    nodes: dict[str, GraphNode],
) -> GraphEdge:
    """
    Build a GraphEdge with deterministic ID and confidence selection.
    """
    confidence = (
        1.0
        if nodes[tgt_id].status == "live"
        else float(nodes[tgt_id].metadata.get("confidence", 0.5))
    )
    return GraphEdge(
        id=edge_id(src_id=src_id, tgt_id=tgt_id, edge_type=edge_type, evidence=evidence),
        source=src_id,
        target=tgt_id,
        type=edge_type,
        confidence=confidence,
        evidence=evidence,
        metadata={},
    )


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
    Find view path usages in parsed view.json structures.

    Targets common patterns:
    - {"props": {"path": "<View/Path>"}}
    - {"viewPath": "<View/Path>"} (page-config style)
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


def _decode_text(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except Exception:
        try:
            return raw.decode("latin-1")
        except Exception:
            return None


def _read_bytes(zip_file: zipfile.ZipFile, zip_path: str) -> bytes | None:
    try:
        return zip_file.read(zip_path)
    except Exception:
        return None
