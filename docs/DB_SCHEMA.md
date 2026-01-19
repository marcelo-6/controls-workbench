# DB_SCHEMA.md - Controls Workbench (SQLite)

## Goals
SQLite stores **queryable state and indexes**. Filesystem stores **large blobs** (uploads + artifact payloads).

SQLite is the source of truth for:
- Jobs (history/state/progress/errors)
- Upload metadata
- Tail-able events (for UI polling)
- Artifact index (what exists, paths, sizes, summary metadata)
- Retention bookkeeping (last_accessed, sizes, deletion flags)

Filesystem stores:
- Uploaded project zips / optional tags json
- Artifact payloads (graph/tree/report/summary/debug logs)

---

## Conventions
- All timestamps are UTC and stored as ISO-8601 text (e.g. `2026-01-15T12:34:56.789Z`)
- IDs are strings (UUIDs recommended)
- JSON is stored as TEXT (serialized JSON) to avoid SQLite JSON-extension dependence
- Foreign keys are enabled (`PRAGMA foreign_keys = ON`)
- Repos use parameterized SQL only

---

## Tables

### 1) `uploads`
Tracks upload blobs stored on disk.

| Column | Type | Notes |
|---|---|---|
| `upload_id` | TEXT PK | UUID string |
| `created_at` | TEXT NOT NULL | UTC ISO |
| `last_accessed_at` | TEXT NOT NULL | updated when used |
| `project_zip_path` | TEXT NOT NULL | absolute or app-relative path |
| `tags_json_path` | TEXT NULL | optional |
| `size_bytes` | INTEGER NOT NULL | total bytes (zip + tags) |
| `sha256` | TEXT NULL | optional, for dedupe |
| `status` | TEXT NOT NULL | `ready`, `deleted` |
| `meta_json` | TEXT NULL | optional JSON (e.g. source info) |

Indexes:
- `idx_uploads_created_at(created_at)`
- `idx_uploads_last_accessed_at(last_accessed_at)`

---

### 2) `jobs`
Primary history/state table. Replaces filesystem scanning.

| Column | Type | Notes |
|---|---|---|
| `job_id` | TEXT PK | UUID string |
| `tool_id` | TEXT NOT NULL | e.g. `ignition.project.explorer` |
| `upload_id` | TEXT NOT NULL FK → uploads(upload_id) | |
| `status` | TEXT NOT NULL | `queued`, `running`, `success`, `failed` |
| `created_at` | TEXT NOT NULL | |
| `started_at` | TEXT NULL | |
| `finished_at` | TEXT NULL | |
| `last_accessed_at` | TEXT NOT NULL | for retention |
| `progress` | INTEGER NULL | 0–100 (optional) |
| `progress_hint` | TEXT NULL | short message |
| `params_json` | TEXT NULL | job parameters/config |
| `error_code` | TEXT NULL | stable error type |
| `error_message` | TEXT NULL | short |
| `error_detail_path` | TEXT NULL | path to full details on disk |
| `artifacts_ready` | INTEGER NOT NULL | 0/1, indicates artifacts finalized |
| `total_artifacts_bytes` | INTEGER NOT NULL | computed for retention |
| `deleted_at` | TEXT NULL | soft delete marker (optional) |

Indexes:
- `idx_jobs_created_at(created_at)`
- `idx_jobs_last_accessed_at(last_accessed_at)`
- `idx_jobs_status(status)`
- `idx_jobs_tool_created(tool_id, created_at)`

Notes:
- Use `last_accessed_at` updates when client views job or downloads artifacts.
- `total_artifacts_bytes` helps retention without scanning directories.

---

### 3) `job_events`
Tail-able events/log lines for a job (used by frontend polling).

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `job_id` | TEXT NOT NULL FK → jobs(job_id) | |
| `ts` | TEXT NOT NULL | UTC ISO |
| `level` | TEXT NOT NULL | `debug`, `info`, `warning`, `error` |
| `kind` | TEXT NULL | e.g. `log`, `state`, `metric` |
| `message` | TEXT NOT NULL | single line or short |
| `payload_json` | TEXT NULL | optional structured data |

Indexes:
- `idx_job_events_job_ts(job_id, ts)`
- `idx_job_events_job_id(id, job_id)` (optional, for incremental paging)

Retention options:
- Keep all events for TTL, or
- Keep last N per job (e.g. 5000) and trim older in maintenance

---

### 4) `job_artifacts`
Index of artifact payloads stored on disk.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `job_id` | TEXT NOT NULL FK → jobs(job_id) | |
| `kind` | TEXT NOT NULL | e.g. `graph`, `tree`, `report`, `summary`, `log`, `debug` |
| `rel_path` | TEXT NOT NULL | path relative to job dir (recommended) |
| `content_type` | TEXT NOT NULL | `application/json`, `text/markdown`, etc. |
| `size_bytes` | INTEGER NOT NULL | |
| `created_at` | TEXT NOT NULL | |
| `meta_json` | TEXT NULL | JSON e.g. node/edge counts, warnings count |

Constraints:
- Unique artifact kind per job is often desired:
  - `UNIQUE(job_id, kind)` (recommended)

Indexes:
- `idx_job_artifacts_job_kind(job_id, kind)`
- `idx_job_artifacts_job(job_id)`

---

## SQL Schema (schema.sql)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS uploads (
  upload_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  last_accessed_at TEXT NOT NULL,
  project_zip_path TEXT NOT NULL,
  tags_json_path TEXT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  meta_json TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_uploads_created_at
  ON uploads(created_at);

CREATE INDEX IF NOT EXISTS idx_uploads_last_accessed_at
  ON uploads(last_accessed_at);

CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  tool_id TEXT NOT NULL,
  upload_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT NULL,
  finished_at TEXT NULL,
  last_accessed_at TEXT NOT NULL,
  progress INTEGER NULL,
  progress_hint TEXT NULL,
  params_json TEXT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  error_detail_path TEXT NULL,
  artifacts_ready INTEGER NOT NULL DEFAULT 0,
  total_artifacts_bytes INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT NULL,
  FOREIGN KEY (upload_id) REFERENCES uploads(upload_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_jobs_created_at
  ON jobs(created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_last_accessed_at
  ON jobs(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_jobs_status
  ON jobs(status);

CREATE INDEX IF NOT EXISTS idx_jobs_tool_created
  ON jobs(tool_id, created_at);

CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  kind TEXT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NULL,
  FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_ts
  ON job_events(job_id, ts);

-- Optional: helps paging by id for a job
CREATE INDEX IF NOT EXISTS idx_job_events_job_id
  ON job_events(job_id, id);

CREATE TABLE IF NOT EXISTS job_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  rel_path TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  meta_json TEXT NULL,
  FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
  UNIQUE(job_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_job_artifacts_job_kind
  ON job_artifacts(job_id, kind);

CREATE INDEX IF NOT EXISTS idx_job_artifacts_job
  ON job_artifacts(job_id);
````

---

## Query patterns (what the repos should support)

### Recent jobs list

* Order by `created_at DESC` (or `last_accessed_at DESC` if you prefer “recently viewed”)
* Filter by `tool_id` optionally
* Exclude soft-deleted rows (`deleted_at IS NULL`)

### Job status

* Read from `jobs` by `job_id`

### Events tail

* `SELECT ... FROM job_events WHERE job_id=? ORDER BY ts DESC LIMIT ?`
* Return reversed (oldest→newest) for UI display

### Artifact list

* `SELECT kind, rel_path, content_type, size_bytes, created_at, meta_json FROM job_artifacts WHERE job_id=?`

### Retention candidate list

* Select jobs where:

  * `deleted_at IS NULL`
  * order by `last_accessed_at ASC`
  * delete oldest until below threshold

---

## Retention policy support

Recommended approach:

1. Maintain `total_artifacts_bytes` in `jobs` (update as artifacts are written/deleted).
2. Retention service queries jobs ordered by `last_accessed_at` and deletes:

   * DB: `DELETE FROM jobs WHERE job_id=?` (cascades events/artifacts)
   * FS: delete job directory + update uploads if no longer referenced
3. Use TTL + max-bytes + max-count (whichever triggers first)

---

## Migrations strategy (simple now, extend later)

### v0 approach (minimal)

* Keep `schema.sql` in repo
* On startup, `init_db()` runs schema idempotently

---

## Future extensions (optional)

* `job_findings` table for structured lint findings (missing refs, unused assets)
* `job_metrics` table for performance metrics (parse time, node counts over time)
* `uploads_refcount` computed column or view to avoid deleting uploads referenced by jobs

