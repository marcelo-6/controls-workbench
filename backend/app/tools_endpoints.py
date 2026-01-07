from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from .api_models import APIModel, APIResponse, ToolsList
from .api_response import ok
from .auth import require_auth
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
