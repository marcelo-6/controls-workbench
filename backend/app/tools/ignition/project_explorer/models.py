# backend/app/tools/ignition/project_explorer/models.py
"""
Ignition Project Explorer graph contracts.

This module defines the JSON-serializable contracts produced by the Ignition
Project Explorer tool. The tool parses an Ignition Designer project export ZIP
and generates a dependency graph for visualization in React Flow.

Design goals:
- Stable, opaque node identifiers suitable for DB indexing and frontend caching.
- Extensible node/edge schemas (typed nodes/edges with metadata, tags, status).
- JSON-safe types only (strings, numbers, booleans, lists, dicts).
- Separation of concerns: the graph contracts are independent of parsing and I/O.

Key concepts:
- GraphNode: Represents a project resource (Perspective view, script, named query, etc.)
- GraphEdge: Represents a dependency/relationship between nodes.
- Graph: A set of nodes and edges.
- GraphBundle: Full tool output including both full graph and UI-filtered graph,
  a Designer-ordered tree model, and summary stats.

Status semantics:
- "live": a resource found in the project export.
- "missing": referenced but not present.
- "derived": inferred/generated helper nodes (e.g., ambiguous reference node).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

NodeStatus = Literal["live", "missing", "derived"]


class GraphNode(BaseModel):
    """
    A typed node representing a project resource.

    Attributes:
        id: Stable, opaque node identifier (UUID string recommended).
        label: Human-readable label for UI.
        type: Node type key (e.g. "perspective.view", "script.python", "named_query").
        path: Resource path within the project (Designer-like path when possible).
        parent_id: Optional parent node id for containment (not dependency).
        status: Node status (live/missing/derived).
        tags: Tags to simplify frontend filtering, grouping, and theming.
        description: Short description.
        details: Optional longer text (safe to show in tooltips/side panel).
        tooltip: Optional concise tooltip.
        metadata: Arbitrary JSON-safe metadata for frontend and diagnostics.
    """

    id: str
    label: str
    type: str
    path: str | None = None
    parent_id: str | None = None

    status: NodeStatus = "live"
    tags: list[str] = Field(default_factory=list)

    description: str | None = None
    details: str | None = None
    tooltip: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """
    A typed edge representing a dependency between nodes.

    Attributes:
        id: Stable edge identifier (UUID string recommended).
        source: Source node id.
        target: Target node id.
        type: Edge type key (e.g. "depends_on", "references", "uses_style_class").
        confidence: Float in [0,1] indicating match certainty for derived references.
        evidence: Short human-readable evidence string.
        metadata: Arbitrary JSON-safe metadata.
    """

    id: str
    source: str
    target: str
    type: str = "references"
    confidence: float = 1.0
    evidence: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    """A dependency graph (nodes + edges)."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TreeNode(BaseModel):
    """
    A UI tree node (Designer-like explorer tree).

    Attributes:
        id: Tree node id (stable string).
        label: Display label.
        kind: "root" | "section" | "folder" | "node".
        children: Child tree nodes.
        node_id: If kind=="node", the referenced graph node id.
        node_type: If kind=="node", the graph node type.
        thumbnail_kind: Optional artifact kind for thumbnail display.
    """

    id: str
    label: str
    kind: Literal["root", "section", "folder", "node"]
    children: list[TreeNode] = Field(default_factory=list)

    node_id: str | None = None
    node_type: str | None = None
    thumbnail_kind: str | None = None


TreeNode.model_rebuild()


class GraphBundle(BaseModel):
    """
    Complete output bundle produced by the Ignition Project Explorer tool.

    Attributes:
        tool_id: Tool identifier (e.g. "ignition.project.explorer").
        generated_at: UTC ISO timestamp.
        project: Minimal project metadata (from project.json).
        profile: Effective profile/settings used to generate graph_ui.
        stats: Summary counts and diagnostics.
        graph_full: Unfiltered graph (all parsed nodes/edges).
        graph_ui: UI-focused filtered graph (based on profile).
        tree: Designer-ordered tree model for project navigation.
    """

    tool_id: str
    generated_at: str

    project: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)

    graph_full: Graph
    graph_ui: Graph
    tree: TreeNode
