from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .api_models import (
    APIModel,
    APIResponse,
    IgnitionNodeDetailsPayload,
    IgnitionSearchResultsPayload,
    IgnitionSubgraphPayload,
    IgnitionTreePayload,
    ToolsList,
)
from .api_response import ok
from .auth import require_auth
from .index_db import get_index_db
from .run_storage import run_dir, touch_meta_access
from .tools_registry import list_tools

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=APIResponse[ToolsList])
def tools(request: Request, user: str = Depends(require_auth)):
    return ok(ToolsList(tools=list_tools()), request_id=getattr(request.state, "request_id", None))


class GraphPayload(APIModel):
    graph: dict


class ReportPayload(APIModel):
    report: dict


class SummaryPayload(APIModel):
    markdown: str


ign = APIRouter(prefix="/api/tools/ignition", tags=["ignition"])


@ign.get("/graph/{job_id}", response_model=APIResponse[GraphPayload])
def get_graph(request: Request, job_id: str, user: str = Depends(require_auth)):
    touch_meta_access(job_id)
    fp = run_dir(job_id) / "graph" / "graph.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Graph not found")
    graph = json.loads(fp.read_text(encoding="utf-8"))
    return ok(GraphPayload(graph=graph), request_id=getattr(request.state, "request_id", None))


@ign.get("/report/{job_id}", response_model=APIResponse[ReportPayload])
def get_report(request: Request, job_id: str, user: str = Depends(require_auth)):
    touch_meta_access(job_id)
    fp = run_dir(job_id) / "report" / "report.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    report = json.loads(fp.read_text(encoding="utf-8"))
    return ok(ReportPayload(report=report), request_id=getattr(request.state, "request_id", None))


@ign.get("/summary/{job_id}", response_model=APIResponse[SummaryPayload])
def get_summary(request: Request, job_id: str, user: str = Depends(require_auth)):
    touch_meta_access(job_id)
    fp = run_dir(job_id) / "report" / "summary.md"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Summary not found")
    return ok(
        SummaryPayload(markdown=fp.read_text(encoding="utf-8")),
        request_id=getattr(request.state, "request_id", None),
    )


# -------------------- Indexed (SQLite) APIs --------------------


@ign.get("/tree/{job_id}", response_model=APIResponse[IgnitionTreePayload])
def get_tree(request: Request, job_id: str, user: str = Depends(require_auth)):
    """Return a Designer-like tree of selectable elements.

    This is built once by the worker and stored in SQLite.
    """
    touch_meta_access(job_id)
    tree = get_index_db().get_tree(job_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    return ok(
        IgnitionTreePayload(tree=tree),
        request_id=getattr(request.state, "request_id", None),
    )


@ign.get("/search/{job_id}", response_model=APIResponse[IgnitionSearchResultsPayload])
def search(
    request: Request, job_id: str, q: str = Query(min_length=1), user: str = Depends(require_auth)
):
    touch_meta_access(job_id)
    matches = get_index_db().search(job_id, q, limit=100)
    return ok(
        IgnitionSearchResultsPayload(matches=matches),
        request_id=getattr(request.state, "request_id", None),
    )


@ign.get("/node/{job_id}/{node_id}", response_model=APIResponse[IgnitionNodeDetailsPayload])
def node_details(request: Request, job_id: str, node_id: str, user: str = Depends(require_auth)):
    touch_meta_access(job_id)
    node = get_index_db().get_node_json(job_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    inbound, outbound = get_index_db().get_edges_for_node(job_id, node_id)
    return ok(
        IgnitionNodeDetailsPayload(node=node, inbound=inbound, outbound=outbound),
        request_id=getattr(request.state, "request_id", None),
    )


@ign.get("/subgraph/{job_id}", response_model=APIResponse[IgnitionSubgraphPayload])
def subgraph(
    request: Request,
    job_id: str,
    root_ids: list[str] = Query(..., description="One or more node ids"),
    depth: int = Query(default=1, ge=0, le=10),
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    max_nodes: int = Query(default=800, ge=10, le=5000),
    user: str = Depends(require_auth),
):
    """Return a pre-sliced graph around the selected roots."""
    touch_meta_access(job_id)
    nodes, edges = get_index_db().subgraph(
        job_id=job_id, roots=root_ids, depth=depth, direction=direction, max_nodes=max_nodes
    )
    graph = {
        "meta": {
            "jobId": job_id,
            "toolId": "ignition.graph",
            "stats": {"nodes": len(nodes), "edges": len(edges)},
        },
        "nodes": nodes,
        "edges": edges,
    }
    return ok(
        IgnitionSubgraphPayload(graph=graph),
        request_id=getattr(request.state, "request_id", None),
    )
