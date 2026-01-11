from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .api_models import ErrorField
from .api_response import fail

# Routers
from .auth import router as auth_router
from .config import settings
from .index_db import get_index_db
from .jobs_endpoints import router as jobs_router
from .jobs_endpoints import runs_router
from .logging_conf import setup_logger
from .logs_endpoints import router as logs_router
from .middleware import RequestIdMiddleware
from .retention import cleanup_runs, cleanup_uploads
from .storage import ensure_dirs
from .tools_endpoints import ign as ignition_router
from .tools_endpoints import router as tools_router
from .uploads_endpoints import router as uploads_router

ensure_dirs()
api_logger = setup_logger("api", str(Path(settings.data_dir) / "logs" / "api.log"))

description = """
# Controls Workbench Web App

## Design Spec v0.1

### Status

* **Locked decisions:** FastAPI backend, React + MUI frontend, React Flow required, Dockerized, users upload files (server never pulls), few trusted users, behind VPN, simple auth, async jobs, **Huey + SQLite** queue (no Redis for now). ([greenlet.readthedocs.io][1])

---

## 1. Purpose and scope

### Vision

A private (VPN-only) web toolbox for controls/automation engineers. The flagship tool is an **Ignition Project Explorer Graph Engine** that parses an **Ignition project export ZIP** (+ optional tag export JSON), builds a unified dependency graph, and renders it in **React Flow**.

### v0.1 flagship outcome

From an uploaded Ignition project export, the system produces:

* `graph.json` (React Flow nodes/edges)
* `report.json` (issues + metrics)
* `summary.md` (human-readable)
  And the UI provides:
* interactive dependency graph (inspect, filter, search)
* unused assets/orphans
* circular dependencies
* broken references
* “blast radius” of changing an entity (view/script/tag/UDT)

### Non-goals (v0.1)

* Enterprise-grade auth/SSO/roles
* Multi-tenant isolation
* Gateway pull/browse (no outbound pulls)
* “Perfect” reference resolution for every Ignition edge-case (we will label confidence)

---

## 2. System architecture

### Services (Docker Compose)

1. **frontend**: React (Vite build) served by **nginx**
2. **api**: FastAPI
3. **worker**: Huey consumer (executes jobs)
4. **data volume**: shared persistent storage

### Why Huey + SQLite

Huey supports **SQLite-backed queue + results** via `SqliteHuey` (uses stdlib `sqlite3`), including a durability option (`fsync`) and documentation noting it can be used safely with multi-process consumers. ([Huey][2])
This avoids Redis now, and keeps a future “desktop mode” much simpler (single file queue DB rather than a broker service).

### Why not FastAPI BackgroundTasks

FastAPI BackgroundTasks are explicitly “run after returning a response” and are excellent for lightweight work, but they are not a durable multi-process worker system. ([FastAPI][3])
You want a real job lifecycle and the ability to run a worker in a separate container.

### High-level flow

```mermaid
flowchart LR
  U[Browser] -->|Upload ZIP/JSON| API[FastAPI]
  API -->|enqueue job| Q[(SQLite queue.db via Huey)]
  W[Worker (Huey consumer)] -->|dequeue + execute| Q
  W -->|write artifacts| FS[(data volume)]
  API -->|serve results/artifacts| U
  API -->|tail logs/events| U
```

---

## 3. Runtime model

### Concurrency assumptions

* 1–3 users total
* Jobs usually **seconds**, occasionally longer but not “many minutes”
* Multiple concurrent jobs allowed, but defaults will avoid thrashing

### Worker model

* Start with **one** worker container, thread workers by default
* Allow scaling by increasing worker container replicas if needed (later)

---

## 4. Storage model

Everything is file-based + a single SQLite DB for the Huey queue/results.

### Data directories (in shared volume)

* `/data/uploads/` – raw uploads (short-lived)
* `/data/runs/` – job artifacts (kept until eviction)
* `/data/queue/queue.db` – Huey SQLite queue/results DB
* `/data/logs/` – API/worker logs (rotating + compressed)

### Run layout

`/data/runs/<job_id>/`

* `meta.json`
* `events.log` (progress lines)
* `inputs/` (optional copy of uploaded files, or references)
* `graph/graph.json`
* `report/report.json`
* `report/summary.md`
* `diff/` (reserved for future)

### `meta.json` (Pydantic-backed)

Contains:

* `job_id`, `tool_id`, `created_at`, `last_accessed_at`
* `input_files`: name, size, hashes
* `versions`: app version, parser version
* `stats`: parse duration, counts

---

## 5. Retention and eviction (“smart deletion”)

### Goals

* Delete runs/uploads older than **X days**
* But also cap by **Y total size** and/or **Z run count**
* Keep “recently used” runs preferentially

### Policy (TTL + LRU hybrid)

Configurable env vars:

* `MAX_AGE_DAYS` (default: 7)
* `MAX_RUNS_BYTES` (default: 5 GB)
* `MAX_RUNS_COUNT` (default: 200)
* `MAX_UPLOAD_AGE_HOURS` (default: 24)

Cleanup algorithm (runs):

1. Compute current totals (bytes + count).
2. If over `MAX_RUNS_BYTES` or `MAX_RUNS_COUNT`, delete runs in ascending `last_accessed_at` until within limits.
3. Then delete runs with `created_at < now - MAX_AGE_DAYS`.

Uploads cleanup:

* delete uploads older than `MAX_UPLOAD_AGE_HOURS`
* also delete orphan uploads not referenced by any run

Implementation note: `last_accessed_at` updates whenever a user opens a run in the UI.

---

## 6. Logging requirements

### Backend logs

Two logs:

* `/data/logs/api.log`
* `/data/logs/worker.log`

Rotation:

* rotate at **20MB**
* keep **5** rotated files
* compress rotated files (`.gz`) after rotation (keep, don’t delete)

### Log UI requirements

* bottom-right footer shows latest log line
* expandable log viewer (bounded: max N lines)
* download logs as a zip: `logs.zip`

---

## 7. Authentication and security

### Threat model

* VPN-only access
* small trusted user base
* simple password protection is acceptable

### Auth design (v0.1)

* Shared password configured via env var
* Login sets a signed session cookie (or short-lived token)
* No per-user isolation needed

### Upload security

* Enforce file size max (e.g., 100MB server-side)
* Only accept:

  * `.zip` for Ignition project export
  * `.json` for tag export
* Safe zip extraction:

  * prevent Zip Slip (no `../` path traversal)
  * extract to a job-scoped directory only

---

## 8. Backend design (FastAPI)

### Component structure (recommended)

* `app/main.py` (FastAPI app, routers)
* `app/auth/` (simple login + dependency)
* `app/uploads/` (upload endpoints + storage)
* `app/jobs/` (job creation, status, events)
* `app/tools/` (tool registry + tool-specific endpoints)
* `app/ignition/` (parser + graph builder)
* `app/logs/` (tail + download)
* `app/retention/` (cleanup scheduler)
* `app/common/` (models, config, utils)

### Why “tools” abstraction (even though v0.1 is one tool)

You want “many mini apps” eventually. So both backend and frontend should treat tools as registered modules with:

* `tool_id`
* input schema
* output artifacts list
* job runner function

---

## 9. Job system (Huey + SQLite)

### Queue instance

Use `SqliteHuey(filename=/data/queue/queue.db, fsync=<bool>)`. ([Huey][2])

* Default `fsync=False` for speed (fine on a VM)
* Make it configurable: `HUEY_FSYNC=true|false`

### Job lifecycle

Stored/derived from:

* Huey task state/results
* Run directory existence + `meta.json`
* `events.log` for progress

States returned to UI:

* `queued`
* `running`
* `success`
* `failed`

### Progress reporting (v0.1)

Worker appends to:

* `/data/runs/<job_id>/events.log`

API exposes:

* `GET /api/jobs/{job_id}/events?tail=N`  (returns last N lines)
  Optionally (v0.2): SSE endpoint streaming events.

---

## 10. API specification (v0.1)

### Auth

* `POST /api/auth/login`

  * body: `{ password: string }`
  * response: `{ ok: true }` + session cookie
* `POST /api/auth/logout`

### Tools

* `GET /api/tools`

  * list tool metadata (id, name, category, version)

### Uploads

* `POST /api/uploads`

  * multipart: `project_zip` (required), `tags_json` (optional)
  * response: `{ upload_id, received_files: [...] }`
* `GET /api/uploads/{upload_id}`

  * metadata only (no raw file download in v0.1 unless needed)

### Jobs

* `POST /api/jobs`

  * body: `{ tool_id: "ignition.graph", upload_id: "...", params: {...} }`
  * response: `{ job_id }`
* `GET /api/jobs/{job_id}`

  * response: `{ status, tool_id, created_at, progress_hint, artifacts_ready }`
* `GET /api/jobs/{job_id}/events?tail=2000`
* `GET /api/jobs/{job_id}/artifacts`

  * returns list: `{ path, size_bytes, url }`

### Tool-specific results (Ignition Graph)

* `GET /api/tools/ignition/graph/{job_id}`

  * returns graph JSON
* `GET /api/tools/ignition/report/{job_id}`

  * returns report JSON
* `GET /api/tools/ignition/summary/{job_id}`

  * returns summary markdown

### Logs

* `GET /api/logs/latest` (single latest line)
* `GET /api/logs/tail?n=2000`
* `GET /api/logs/download` (zip)

---

## 11. Frontend design (React + MUI + React Flow)

### UI layout (v0.1)

* Left nav (collapsible):

  * categories (Ignition only initially)
  * tool list
* Main workspace:

  * tool page content
* Bottom-left expandable “Output”:

  * job events tail + warnings
* Bottom-right “Latest Log”:

  * latest line + expand for log viewer + download logs
* Toast notifications:

  * upload success/failure
  * job started/completed/failed

### Pages/routes (v0.1)

* `/login`
* `/tools/ignition/graph`

  * upload panel
  * run history (recent runs)
  * React Flow graph canvas + inspector + issues tables

### Graph UX requirements

* Search box for nodes (fuzzy match by label/path)
* Filters (toggle layers):

  * Views / Scripts / Queries / Tags / UDTs (as available)
* Inspector panel (right-side inside main area is fine v0.1):

  * selected node details
  * inbound/outbound edges
  * “blast radius” action:

    * forward impact
    * reverse impact

---

## 12. Flagship tool spec: Ignition Project Explorer Graph Engine

### Inputs

* Ignition project export ZIP (required)
* Tag export JSON (optional in v0.1; integrate in v0.2 if it slows you down)

### Supported artifacts to parse (incremental confidence model)

We will produce edges with a `confidence` field:

* `high`: deterministic structured references
* `medium`: known patterns with low ambiguity
* `low`: regex/string heuristics

#### v0.1 parsing scope (recommended)

1. **Perspective views**

   * parse `view.json`
   * extract:

     * embedded view references
     * project resource references (where explicit)
     * tag path occurrences (best effort)
2. **Scripts**

   * scan project/gateway/shared scripts for:

     * known Ignition calls (best effort)
     * tag path literals / view path literals
3. **Named queries**

   * index names and references (best effort)

#### v0.2+ scope

* Vision windows
* SFC xml references
* UDT definitions + instances
* themes/styles/templates
* tag event scripts (if included in export)

### Core output: `graph.json`

**Top-level**

* `meta`: `{ tool_id, job_id, created_at, parser_version, stats }`
* `nodes`: array
* `edges`: array

**Node model (example)**

* `id`: stable string (e.g., hash of type + path)
* `type`: `"view" | "script" | "query" | "tag" | "udt" | "resource"`
* `label`: short label
* `path`: canonical project path
* `data`:

  * `kind` (subtype)
  * `source_file` (relative path)
  * `metrics` (counts, size, etc.)

**Edge model (example)**

* `id`
* `source`
* `target`
* `type`: `"references" | "embeds" | "reads" | "writes" | "calls"`
* `confidence`: `"high" | "medium" | "low"`
* `evidence`: short snippet or JSON pointer (bounded length)

### Analyses computed

* **Orphans/unused**: nodes with 0 inbound edges (with allowlist of “roots”)
* **Broken references**: edge targets not found in node index
* **Cycles**: strongly connected components size > 1
* **Blast radius**:

  * forward traversal (impact of change)
  * reverse traversal (what depends on this)

### `report.json`

* `stats`: counts by node/edge type
* `issues`:

  * `orphans[]`
  * `broken_refs[]`
  * `cycles[]`
* `top_lists`:

  * most-referenced nodes
  * largest views/scripts
  * highest fan-out/fan-in

### `summary.md`

Human readable:

* project totals
* top hotspots
* key issues (orphans, cycles, broken refs)
* timestamps + tool version

---

## 13. Deployment spec (Docker Compose)

### Containers

* `frontend`:

  * nginx static hosting
  * reverse proxy `/api` → `api:8000`
* `api`:

  * FastAPI, Uvicorn
* `worker`:

  * Huey consumer process

### Environment variables (examples)

* `APP_PASSWORD`
* `DATA_DIR=/data`
* `HUEY_DB=/data/queue/queue.db`
* `HUEY_FSYNC=false`
* `MAX_AGE_DAYS=7`
* `MAX_RUNS_BYTES=5368709120`
* `MAX_RUNS_COUNT=200`
* `LOG_MAX_BYTES=20971520`
* `LOG_BACKUP_COUNT=5`

---

## 14. Development plan and milestones

### v0.1 milestones

1. Repo skeleton + docker compose + nginx proxy
2. Auth (simple password) + basic UI shell
3. Upload API + store files safely
4. Huey worker running + job submission/status/events
5. Parser v0: build a minimal graph from a small sample project
6. React Flow canvas rendering from `graph.json`
7. Inspector + issues tables + blast radius
8. Retention cleanup job
9. Logging rotation + log UI + download logs

### Success criteria for v0.1

* Upload → job → graph rendered in React Flow reliably
* Clear outputs + repeatable runs
* Debuggable (events + logs)
* Doesn’t grow storage unbounded

---

## 15. Future direction (kept compatible by design)

### Plotly

* Add report charts (hotspots, distributions) either:

  * server generates plotly JSON
  * frontend renders plotly.js
* No architecture changes required

### Desktop mode (far-ish future)

* Tauri shell that points to:

  * either local server mode (FastAPI running locally)
  * or remote VM mode
* Optional PyInstaller sidecar for local backend
* SQLite Huey queue remains compatible (single-file queue)

### API Modeling Standard

- All endpoints return `APIResponse[T]`
- camelCase JSON aliases
- global exception handlers wrap errors into `APIResponse[None]`
- request IDs in `meta.requestId` + header `X-Request-Id`

### API contract standard
Envelope for every response

Every endpoint returns the same top-level shape:

```json
{
  "status": "success",
  "message": "optional human message",
  "data": { /* endpoint-specific payload */ },
  "meta": { /* optional */ },
  "error": null
}
```


On error:

```json

{
  "status": "error",
  "message": "Validation failed",
  "data": null,
  "meta": { "requestId": "..." },
  "error": {
    "code": "VALIDATION_ERROR",
    "detail": "Request body validation failed",
    "fields": [
      { "field": "projectZip", "message": "Field required" }
    ]
  }
}
```
#### Naming convention

Python: snake_case field names
JSON: camelCase (easier in TS/React)
Pydantic handles conversion via alias_generator.
"""

app = FastAPI(title="Controls Workbench API", version="0.1.0", description=description)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(code="HTTP_ERROR", detail=str(exc.detail), request_id=rid).model_dump(
            mode="json", by_alias=True
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None)
    fields = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        fields.append(ErrorField(field=loc or "body", message=err.get("msg", "Invalid value")))
    resp = fail(
        code="VALIDATION_ERROR",
        detail="Request validation failed",
        request_id=rid,
        fields=fields,
    )
    return JSONResponse(status_code=422, content=resp.model_dump(mode="json", by_alias=True))


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    api_logger.exception("Unhandled error request_id=%s: %s", rid, exc)
    resp = fail(code="INTERNAL_ERROR", detail="Internal server error", request_id=rid)
    return JSONResponse(status_code=500, content=resp.model_dump(mode="json", by_alias=True))


# Include routers
app.include_router(auth_router)
app.include_router(uploads_router)
app.include_router(jobs_router)
app.include_router(runs_router)
app.include_router(tools_router)
app.include_router(ignition_router)
app.include_router(logs_router)


async def _retention_loop():
    # small, safe loop; deletes old uploads and trims runs
    while False:  # TODO this should be run once when the user uploads something
        try:
            del_uploads = cleanup_uploads()
            run_stats = cleanup_runs()
            api_logger.info("retention: deleted_uploads=%s stats=%s", del_uploads, run_stats)
        except Exception as e:
            api_logger.exception("retention loop error: %s", e)
        await asyncio.sleep(60 * 60)  # hourly


@app.on_event("startup")
async def _startup():
    api_logger.info("API startup")
    # Initialize the SQLite catalog early (creates schema if missing).
    try:
        get_index_db()
    except Exception as e:
        api_logger.exception("Index DB init failed: %s", e)
    asyncio.create_task(_retention_loop())
