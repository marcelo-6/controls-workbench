-- backend/app/infra/db/schema.sql
--
-- Controls Workbench - SQLite Schema (Source of Truth)
--
-- Purpose
-- -------
-- This file defines the canonical SQLite schema for the Controls Workbench backend.
-- It is the *single source of truth* for all database structures used to store
-- queryable application state and indexes.
--
-- What belongs in the DB vs filesystem
-- -----------------------------------
-- DB (this schema) stores *queryable state*:
--   - Upload metadata (identifiers, timestamps, paths, hashes, sizes)
--   - Job lifecycle state (status, progress, errors, timestamps)
--   - Job events (tail-able log lines for UI polling)
--   - Artifact index (what artifacts exist for a job + lightweight metadata)
--
-- Filesystem stores *blob payloads*:
--   - Uploaded files (project zip, optional tags json)
--   - Generated artifacts (graph JSON, tree index, reports, summaries, etc.)
--
-- Operational notes
-- -----------------
-- - This schema is applied idempotently at startup via `infra/db/db.py:init_db()`.
--   The app currently uses a "schema.sql as migrations" strategy (v0).
-- - Timestamps are stored as UTC ISO-8601 strings in TEXT columns to keep the
--   database portable and JSON-safe.
-- - Foreign keys are enforced (`PRAGMA foreign_keys = ON`) and cascades are used
--   where appropriate (e.g., deleting a job deletes its events/artifacts).
-- - WAL mode and other connection pragmas are set at connection time (not here)
--   to improve concurrency and reliability.
--
-- Changing the schema
-- -------------------
-- - Keep changes backwards-compatible until you intentionally introduce a
--   migration strategy (future work).
-- - Add/adjust repository tests under `backend/tests/unit/infra/db/` to lock
--   expected behavior.
--
-- PRAGMA foreign_keys = ON;

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
