# Controls Workbench — Project Design Guidelines

## Purpose
Controls Workbench is a personal toolbox for controls/automation engineers. v0.x prioritizes:
- Maintainability over premature optimization
- Clear separation of concerns
- Uniform API responses
- High test coverage (95–99% target)
- Simple local + Docker-based development

## Core Architecture
This project follows a layered architecture:

1. **API Layer (FastAPI)**
   - Routing, request validation, response serialization
   - No business logic
   - No direct filesystem or DB access
   - Delegates to domain services

2. **Domain Layer (Services + Domain Models)**
   - Pure application logic (HTTP-independent)
   - Orchestrates workflows: jobs, uploads, tools
   - Calls infra via repositories/ports
   - Unit-test first

3. **Infrastructure Layer**
   - SQLite repositories for persistence and queryable state
   - Filesystem “blob store” for uploads/artifacts
   - Queue runner (Huey in prod, synchronous runner for tests)

4. **Tools Layer**
   - Isolated tool implementations (e.g., Ignition graph engine)
   - Prefer pure functions
   - Golden file tests for parsers/indexers

## Source of Truth Rules
- **SQLite is the source of truth** for:
  - Job state/history
  - Upload metadata
  - Event logs (tail)
  - Artifact index (what artifacts exist + metadata)
- **Filesystem is the blob store** for:
  - Uploaded files (zips/json)
  - Artifact payloads (graph.json, tree.json, reports, summaries)
  - Large debug logs

## Project Structure
Target structure:

```plain
backend/
  app/
    main.py
    core/
      settings.py
      version.py
      logging.py
      middleware.py
      responses.py
      errors.py
      time.py
    api/
      router.py
      deps.py
      routes/
        auth.py
        jobs.py
        uploads.py
        events.py
        artifacts.py
        logs.py
        tools.py
      schemas/
        common.py
        auth.py
        jobs.py
        uploads.py
        events.py
        artifacts.py
        tools.py
    domain/
      auth/
        service.py
        models.py
      jobs/
        service.py
        models.py
      uploads/
        service.py
        models.py
      tools/
        registry.py
        service.py
        models.py
    infra/
      db/
        schema.sql
        db.py
        repos/
          jobs_repo.py
          uploads_repo.py
          events_repo.py
          artifacts_repo.py
      storage/
        paths.py
        uploads_fs.py
        artifacts_fs.py
        retention.py
      queue/
        runner.py
        huey_app.py
        tasks.py
    tools/
      ignition_graph/
        engine.py
        parser.py
        indexing.py
        models.py
        service.py
        util.py
tests/
  unit/
  integration/
  conftest.py
````

## Naming Conventions

* Packages: `snake_case`
* Modules: `snake_case.py`
* Classes: `PascalCase`
* Functions: `snake_case`
* Constants: `UPPER_SNAKE_CASE`
* Tool IDs: `namespace.tool_name` (e.g., `ignition.graph`)

## API Design Conventions

### Uniform response contract

All endpoints return:

```json
{
  "status": "success|error",
  "message": "optional",
  "data": { },
  "meta": { "request_id": "...", "ts": "..." },
  "error": { "code": "...", "detail": "...", "fields": {...} }
}
```

* Success: `status=success`, `error=null`
* Error: `status=error`, `data=null`, `error` populated

### Endpoint conventions

* Use **nouns** for resources:

  * `/api/jobs`
  * `/api/uploads`
  * `/api/jobs/{job_id}/events`
  * `/api/jobs/{job_id}/artifacts`
* Prefer consistent parameter names:

  * `job_id`, `upload_id`

### Sync vs async

* FastAPI routes can be `async def` but must not block:

  * DB/FS operations should be in service/infra
  * If sync I/O is used, call via `run_in_threadpool` when necessary
* CPU-intensive parsing should run in the worker (Huey), not inside request handler.

## Persistence Conventions (SQLite)

* Prefer SQL queries in repositories; services don’t write SQL
* Keep “queryable state” in DB, “large blobs” in files
* All timestamps are UTC ISO-8601
* Use explicit indexes for frequent queries:

  * events tail by job_id
  * recent jobs ordered by created_at/last_accessed_at

## Testing Strategy

### Coverage targets

* Domain/services/tools: 95–100%
* Infra/storage: 90–100%
* API routes: thin; tested mainly via integration flows
* Overall: 95%+ target, ratchet up over time

### Test types

* Unit tests:

  * services (business rules)
  * repos (DB operations against temp sqlite)
  * storage (tmp_path FS)
  * tool parsing/indexing (golden fixtures)
* Integration tests:

  * 3–5 high-value flows: auth, upload+job lifecycle, events tail, artifacts list

### Determinism requirements

* Tests must not require external services (no separate worker required)
* Use a synchronous queue runner in tests

## Documentation + Docstrings

* Public functions/classes must have docstrings (Google style)
* Complex logic: add “why” comments, not “what”
* Keep docs in `docs/`:

  * Design guideline (this doc)
  * Backend refactor plan
  * Tool-specific docs (Ignition graph format, etc.)

## Coding Standards

* Ruff for lint/format
* Type hints everywhere (especially service boundaries)
* Avoid global state except settings singletons
* Prefer dependency injection via FastAPI `Depends` at the API boundary only