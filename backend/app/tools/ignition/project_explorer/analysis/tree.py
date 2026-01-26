"""
Designer-like tree construction.

The tree is used by the frontend to browse resources. Every leaf node includes
a stable `node_id` so the UI can:
- load subgraphs from a selected resource
- pan/zoom/highlight the corresponding node in a graph view
"""

from __future__ import annotations

from app.tools.ignition.project_explorer.constants import (
    SECTION_ORDER,
    TYPE_PERSPECTIVE_VIEW,
)
from app.tools.ignition.project_explorer.models import GraphNode, TreeNode
from app.tools.ignition.project_explorer.util import normalize_ignition_path

from .ids import folder_id


def build_tree(*, project_title: str, nodes: dict[str, GraphNode]) -> TreeNode:
    """
    Build a tree containing only present sections, ordered by SECTION_ORDER.

    Unknown sections are appended alphabetically at the end.
    """
    root = TreeNode(id="root", label=project_title or "Project", kind="root", children=[])

    section_to_items: dict[str, list[GraphNode]] = {}
    for n in nodes.values():
        if n.status != "live":
            continue
        sec = str(n.metadata.get("section") or "Other")
        section_to_items.setdefault(sec, []).append(n)

    ordered_sections = [s for s in SECTION_ORDER if s in section_to_items]
    for s in sorted(section_to_items.keys()):
        if s not in ordered_sections:
            ordered_sections.append(s)

    for sec in ordered_sections:
        sec_node = TreeNode(id=f"sec:{sec}", label=sec, kind="section", children=[])
        items = section_to_items.get(sec, [])
        items.sort(key=lambda x: normalize_ignition_path(x.path or x.label))

        for n in items:
            _insert_into_section_tree(sec_node, n)

        if sec_node.children:
            root.children.append(sec_node)

    return root


def _insert_into_section_tree(section_node: TreeNode, node: GraphNode) -> None:
    """
    Insert a node into its section subtree based on its path segments.
    """
    path = normalize_ignition_path(node.path or "")
    parts = [p for p in path.split("/") if p]

    leaf_label = parts[-1] if parts else node.label
    folders = parts[:-1]

    cur = section_node
    acc = []
    for f in folders:
        acc.append(f)
        child = next(
            (c for c in (cur.children or []) if c.kind == "folder" and c.label == f),
            None,
        )
        if not child:
            child = TreeNode(
                id=folder_id(section_id=section_node.id, folder_path="/".join(acc)),
                label=f,
                kind="folder",
                children=[],
            )
            cur.children.append(child)
        cur = child

    thumb_kind = f"node:{node.id}:thumbnail" if node.type == TYPE_PERSPECTIVE_VIEW else None

    leaf = TreeNode(
        id=f"node:{node.id}",
        label=leaf_label,
        kind="node",
        node_id=node.id,
        node_type=node.type,
        thumbnail_kind=thumb_kind,
    )
    cur.children.append(leaf)
