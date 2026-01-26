"""
Stable identifier helpers for the analysis layer.

All IDs must be deterministic across runs to enable:
- cacheable frontend behavior
- consistent pan/zoom/highlight targets
- reproducible tests and snapshots
"""

from __future__ import annotations

from app.tools.ignition.project_explorer.util import (
    normalize_ignition_path,
    stable_uuid5,
)


def node_id(*, type_key: str, logical_path: str) -> str:
    """
    Compute a stable node ID for a resource.

    Args:
        type_key: Resource type key (e.g., "perspective.view").
        logical_path: Designer-like logical path (e.g., "Exchange/Dash/Dash").

    Returns:
        Stable UUID5 string.
    """
    return stable_uuid5("node", type_key, normalize_ignition_path(logical_path))


def edge_id(*, src_id: str, tgt_id: str, edge_type: str, evidence: str) -> str:
    """
    Compute a stable edge ID.

    Evidence is included to keep IDs deterministic even if multiple edges connect
    the same source/target with different reasons.
    """
    return stable_uuid5("edge", src_id, tgt_id, edge_type, evidence)


def folder_id(*, section_id: str, folder_path: str) -> str:
    """
    Compute a stable tree folder node ID.
    """
    return stable_uuid5("tree-folder", section_id, normalize_ignition_path(folder_path))
