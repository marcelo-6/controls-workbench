"""
Reference resolution for the analysis layer.

This module resolves "path-like" references to:
- exact existing nodes
- suffix-matched existing nodes
- ambiguous derived nodes
- missing derived nodes

Confidence scoring lives here and is explicit.
"""

from __future__ import annotations

from app.tools.ignition.project_explorer.models import GraphNode
from app.tools.ignition.project_explorer.util import (
    best_effort_suffix_candidates,
    normalize_ignition_path,
    stable_uuid5,
)


def resolve_path_reference(
    *,
    ref_kind: str,
    ref_value: str,
    nodes_by_norm_path: dict[str, list[str]],
    nodes: dict[str, GraphNode],
    expected_type_prefix: str | None,
) -> str:
    """
    Resolve a path-like reference into a target node id.

    Strategy:
    1) exact normalized match
    2) suffix match (best-effort)
    3) missing node

    If multiple candidates are found at any stage, create an ambiguous derived node.

    Returns:
        target node id (live, derived, or missing)
    """
    ref_norm = normalize_ignition_path(ref_value)
    if not ref_norm:
        return missing_node(nodes, ref_kind=ref_kind, ref_value=ref_value, confidence=0.2)

    # 1) exact match
    exact_ids = _filter_by_type_prefix(
        nodes, nodes_by_norm_path.get(ref_norm, []), expected_type_prefix
    )
    if len(exact_ids) == 1:
        return exact_ids[0]
    if len(exact_ids) > 1:
        return ambiguous_node(
            nodes,
            ref_kind=ref_kind,
            ref_value=ref_value,
            candidates=exact_ids,
            confidence=0.9,
        )

    # 2) suffix match
    all_paths = list(nodes_by_norm_path.keys())
    suffix_paths = best_effort_suffix_candidates(ref_norm, all_paths)
    suffix_ids: list[str] = []
    for sp in suffix_paths:
        suffix_ids.extend(nodes_by_norm_path.get(normalize_ignition_path(sp), []))
    suffix_ids = _filter_by_type_prefix(nodes, suffix_ids, expected_type_prefix)
    suffix_ids = list(dict.fromkeys(suffix_ids))  # stable unique
    if len(suffix_ids) == 1:
        nid = suffix_ids[0]
        # Mark that this was not an exact match.
        nodes[nid].metadata.setdefault("confidence", 0.6)
        return nid
    if len(suffix_ids) > 1:
        return ambiguous_node(
            nodes,
            ref_kind=ref_kind,
            ref_value=ref_value,
            candidates=suffix_ids,
            confidence=0.6,
        )

    # 3) missing
    return missing_node(nodes, ref_kind=ref_kind, ref_value=ref_value, confidence=0.4)


def missing_node(
    nodes: dict[str, GraphNode], *, ref_kind: str, ref_value: str, confidence: float
) -> str:
    """
    Create or return a deterministic "missing" node.
    """
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


def ambiguous_node(
    nodes: dict[str, GraphNode],
    *,
    ref_kind: str,
    ref_value: str,
    candidates: list[str],
    confidence: float,
) -> str:
    """
    Create or return a deterministic "ambiguous" derived node.
    """
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


def _filter_by_type_prefix(
    nodes: dict[str, GraphNode], ids: list[str], prefix: str | None
) -> list[str]:
    if not prefix:
        return ids
    return [i for i in ids if nodes.get(i) and nodes[i].type.startswith(prefix)]
