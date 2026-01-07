from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parser_version: str = "0.1.0"
    stats: Dict[str, Any] = Field(default_factory=dict)


class GraphNode(APIModel):
    id: str
    type: str  # view|script|query|tag|udt|resource
    label: str
    path: str
    data: Dict[str, Any] = Field(default_factory=dict)
    # ReactFlow needs a position; frontend will re-layout
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class GraphEdge(APIModel):
    id: str
    source: str
    target: str
    type: EdgeType = "references"
    confidence: Confidence = Confidence.low
    evidence: Optional[str] = None


class GraphDoc(APIModel):
    meta: GraphMeta
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
