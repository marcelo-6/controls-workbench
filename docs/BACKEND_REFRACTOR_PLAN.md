# Backend Refactor Plan - Controls Workbench (DB-first)

## Objective
Refactor the backend into a clean FastAPI + modern Python architecture with:
- Thin API layer (routing only)
- Domain services for business logic
- Infra repositories for SQLite and FS blob store
- Uniform APIResponse contract everywhere
- 95–99% test coverage path
- Bulk changes allowed (no external users)

## Current State (baseline)
Current backend is mostly flat with:
- endpoints and logic mixed
- path building duplicated and sometimes string-based
- run history inferred from filesystem
- missing clear DB ownership boundaries

## Target State
- Rename “runs” → “jobs” across API and backend
- SQLite stores all job/upload state and indexes
- Filesystem stores uploads + artifacts payloads
- Huey used for background processing; tests run tasks synchronously

---

## Phase 0 - Testing Foundation (must come first)
### Goals
- Create a safety harness so bulk changes remain safe.

### Deliverables
- Add/confirm test deps:
  - pytest, pytest-cov, pytest-asyncio, httpx
- Add coverage config and initial gates (start ~85%)
- Create core fixtures:
  - `tmp_path` base dirs for storage
  - temp sqlite DB path
  - settings override fixture
  - FastAPI app factory
  - httpx AsyncClient fixture
- Add 3–5 integration tests:
  1. health endpoint
  2. auth login/me/logout
  3. upload → create job → poll status → list artifacts
  4. events tail
  5. error response shape

### Validation
- Tests run locally in <10–15 seconds
- Coverage report generated and stored as baseline

---

## Phase 1 - Introduce SQLite schema + repositories (DB layer first)
### Goals
- Establish DB as the future source of truth before moving endpoints.

### Deliverables
- `infra/db/schema.sql` and `init_db()` logic (or minimal migration mechanism)
- Repos (DB access only; no business logic):
  - `JobsRepo`
  - `UploadsRepo`
  - `EventsRepo`
  - `ArtifactsRepo`

### Minimal schema
- `uploads`
- `jobs`
- `job_events`
- `job_artifacts`

### Validation
- Unit tests for repositories using a temp sqlite db
- CRUD + key queries covered (recent jobs, events tail, artifacts list)

---

## Phase 2 - Mechanical restructure (move files to target layout)
### Goals
- Create new folders and relocate modules with minimal behavior changes.

### Deliverables
- Create package skeleton:
  - `core/`, `api/`, `domain/`, `infra/`, `tools/`
- Move modules (imports updated) without rewriting logic yet
- Keep app bootable and tests passing

### Validation
- App starts
- Integration tests still pass

---

## Phase 3 - Storage boundary + Path normalization
### Goals
- Eliminate string/path bugs and stop building paths outside storage.

### Deliverables
- `infra/storage/paths.py` is the only path factory
- `uploads_fs.py` handles saving/reading upload blobs
- `artifacts_fs.py` handles artifact payload read/write
- No endpoint/service constructs filesystem paths directly

### Validation
- Unit tests for `paths.py`, `uploads_fs.py`, `artifacts_fs.py`
- Grep rule: no `Path(` outside `infra/storage/*` (except tests)

---

## Phase 4 - Standardize APIResponse + global error handling
### Goals
- Every endpoint returns the same contract, including errors.
- Datetimes are always JSON safe.

### Deliverables
- `core/responses.py`: `APIResponse[T]`, `ok()`, `fail()`
- `core/errors.py`: exception classes + mapping to API error codes
- Global exception handler uses `model_dump(mode="json")` (or `jsonable_encoder`)

### Validation
- Integration test: forced exception returns uniform APIResponse error
- No `datetime not JSON serializable` errors

---

## Phase 5 - Extract domain services; make API layer thin
### Goals
- Convert each endpoint group to: Router → Service → Repo/Storage

### Order
1. uploads
2. jobs lifecycle (create/status)
3. events tail
4. artifacts list/download
5. logs endpoints
6. tools registry/dispatch

### Validation
- Service functions are unit-tested
- Endpoints become glue only
- Integration tests stay green

---

## Phase 6 - Queue/task modernization (Huey + sync runner for tests)
### Goals
- Background execution is clean; tests are deterministic.

### Deliverables
- `infra/queue/runner.py`:
  - prod runner uses Huey enqueue
  - test runner runs inline
- `infra/queue/tasks.py` calls domain services only
- Persist job state transitions in DB:
  - queued → running → success/failed
- Persist event lines and artifact index to DB

### Validation
- “upload → job → run sync → artifacts” integration test passes without separate worker

---

## Phase 7 - Tool module hardening (Ignition Graph)
### Goals
- Make ignition tool code pure and heavily tested.

### Deliverables
- Golden test fixtures (small ignition export zips)
- Tests for:
  - parsing
  - indexing/tree build
  - graph generation
  - missing references + findings
- Store graph/tree/report payloads to FS; store counts/index to DB

### Validation
- Tool module coverage ~95–100%
- Outputs stable across runs

---

## Coverage Ratchet Plan
- Start gate: 85%
- After Phase 4: 90%
- After Phase 6: 95%
- After Phase 7: 98–99% target

---

## Migration Notes
### Rename “runs” → “jobs”
- API paths should become `/api/jobs/*`
- DB tables use `jobs`
- Frontend can be updated alongside since no users exist

### DB vs FS ownership
- DB holds metadata/state/indexes/events
- FS holds large blobs (uploads/artifacts)

### “Done” means
- Tests green
- Coverage gate met
- No mixed concerns (routers don’t do I/O or business logic)
