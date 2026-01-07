from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field

from ..api_models import APIModel


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


EdgeType = Literal["references", "embeds", "reads", "writes", "calls"]


class GraphMeta(APIModel):
    tool_id: str = "ignition.graph"
    job_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parser_version: str = "0.1.0"
    stats: dict[str, Any] = Field(default_factory=dict)


class GraphNode(APIModel):
    id: str
    type: str  # view|script|query|tag|udt|resource
    label: str
    path: str
    data: dict[str, Any] = Field(default_factory=dict)
    # ReactFlow needs a position; frontend will re-layout
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class GraphEdge(APIModel):
    id: str
    source: str
    target: str
    type: EdgeType = "references"
    confidence: Confidence = Confidence.low
    evidence: str | None = None


class GraphDoc(APIModel):
    meta: GraphMeta
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
