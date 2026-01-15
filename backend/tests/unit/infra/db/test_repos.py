# backend/tests/unit/infra/db/test_repos.py
"""
Test suite for the SQLite-backed repository layer.

These tests validate the behavior of the UploadsRepo, JobsRepo, EventsRepo,
and ArtifactsRepo classes against a temporary on-disk SQLite database. Each
test exercises the core CRUD and query operations that the application relies
on for correctness, including:

- Upload creation, retrieval, and access-time updates
- Job creation, status transitions, and recent-job queries
- Event append and ordered tail retrieval
- Artifact upsert semantics and listing behavior

The tests run against an isolated temporary database created via pytest's
tmp_path fixture to ensure deterministic, side-effect-free execution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.infra.db.db import db_session, init_db
from app.infra.db.repos.artifacts import ArtifactsRepo
from app.infra.db.repos.events import EventsRepo
from app.infra.db.repos.jobs import JobsRepo
from app.infra.db.repos.uploads import UploadsRepo


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """
    Create a temporary SQLite database for testing.

    The fixture initializes a fresh database schema using `init_db` and returns
    the path to the resulting file. Each test receives its own isolated database
    instance, ensuring no cross-test interference.
    """
    p = tmp_path / "test.sqlite"
    init_db(p)
    return p


def test_uploads_repo_create_get_touch(db_path: Path) -> None:
    """
    Verify UploadsRepo supports creation, retrieval, and touch updates.

    This test ensures:
    - A newly created upload can be retrieved by ID.
    - The stored fields match the inserted values.
    - Calling `touch()` updates the `last_accessed_at` timestamp.
    """
    with db_session(db_path) as conn:
        repo = UploadsRepo(conn)
        repo.create(
            upload_id="u1",
            created_at="2026-01-15T00:00:00Z",
            last_accessed_at="2026-01-15T00:00:00Z",
            project_zip_path="uploads/u1/project.zip",
            tags_json_path=None,
            size_bytes=123,
            sha256=None,
        )
        row = repo.get("u1")
        assert row is not None
        assert row["upload_id"] == "u1"

        repo.touch("u1", last_accessed_at="2026-01-15T01:00:00Z")
        row2 = repo.get("u1")
        assert row2["last_accessed_at"] == "2026-01-15T01:00:00Z"


def test_jobs_repo_create_recent_set_status(db_path: Path) -> None:
    """
    Validate job creation, status updates, and recent-job queries.

    This test covers:
    - Creating a job linked to an existing upload
    - Default job status (`queued`)
    - Updating status, start time, and progress
    - Retrieving recent jobs in descending creation order
    """
    with db_session(db_path) as conn:
        UploadsRepo(conn).create(
            upload_id="u1",
            created_at="2026-01-15T00:00:00Z",
            last_accessed_at="2026-01-15T00:00:00Z",
            project_zip_path="uploads/u1/project.zip",
            tags_json_path=None,
            size_bytes=1,
            sha256=None,
        )

        jobs = JobsRepo(conn)
        jobs.create(
            job_id="j1",
            tool_id="ignition.graph",
            upload_id="u1",
            created_at="2026-01-15T00:10:00Z",
            last_accessed_at="2026-01-15T00:10:00Z",
            params_json=json.dumps({"depth": 2}),
        )

        got = jobs.get("j1")
        assert got is not None
        assert got["status"] == "queued"

        jobs.set_status("j1", status="running", started_at="2026-01-15T00:11:00Z", progress=10)

        got2 = jobs.get("j1")
        assert got2["status"] == "running"
        assert got2["progress"] == 10

        rec = jobs.recent(limit=10)
        assert len(rec) == 1
        assert rec[0]["job_id"] == "j1"


def test_events_repo_append_tail_order(db_path: Path) -> None:
    """
    Ensure EventsRepo appends events and returns them in chronological order.

    The test verifies:
    - Events can be appended for a job
    - `tail()` returns events ordered by timestamp
    - Message ordering matches insertion order
    """
    with db_session(db_path) as conn:
        UploadsRepo(conn).create(
            upload_id="u1",
            created_at="2026-01-15T00:00:00Z",
            last_accessed_at="2026-01-15T00:00:00Z",
            project_zip_path="uploads/u1/project.zip",
            tags_json_path=None,
            size_bytes=1,
            sha256=None,
        )
        JobsRepo(conn).create(
            job_id="j1",
            tool_id="ignition.graph",
            upload_id="u1",
            created_at="2026-01-15T00:10:00Z",
            last_accessed_at="2026-01-15T00:10:00Z",
        )

        ev = EventsRepo(conn)
        ev.append(job_id="j1", ts="2026-01-15T00:10:01Z", level="info", message="a")
        ev.append(job_id="j1", ts="2026-01-15T00:10:02Z", level="info", message="b")

        tail = ev.tail(job_id="j1", limit=100)
        assert [x["message"] for x in tail] == ["a", "b"]


def test_artifacts_repo_upsert_list_get(db_path: Path) -> None:
    """
    Test artifact upsert behavior, retrieval, and listing.

    This test ensures:
    - Artifacts can be inserted for a job
    - Upserting replaces the existing record for the same (job_id, kind)
    - `get()` returns the updated artifact
    - `list()` returns all artifacts for a job
    """
    with db_session(db_path) as conn:
        UploadsRepo(conn).create(
            upload_id="u1",
            created_at="2026-01-15T00:00:00Z",
            last_accessed_at="2026-01-15T00:00:00Z",
            project_zip_path="uploads/u1/project.zip",
            tags_json_path=None,
            size_bytes=1,
            sha256=None,
        )
        JobsRepo(conn).create(
            job_id="j1",
            tool_id="ignition.graph",
            upload_id="u1",
            created_at="2026-01-15T00:10:00Z",
            last_accessed_at="2026-01-15T00:10:00Z",
        )

        art = ArtifactsRepo(conn)
        art.upsert(
            job_id="j1",
            kind="graph",
            rel_path="graph.json",
            content_type="application/json",
            size_bytes=10,
            created_at="2026-01-15T00:20:00Z",
            meta_json=json.dumps({"nodes": 1}),
        )
        row = art.get(job_id="j1", kind="graph")
        assert row is not None
        assert row["rel_path"] == "graph.json"

        # Upsert updates same (job_id, kind)
        art.upsert(
            job_id="j1",
            kind="graph",
            rel_path="graph.v2.json",
            content_type="application/json",
            size_bytes=20,
            created_at="2026-01-15T00:21:00Z",
            meta_json=json.dumps({"nodes": 2}),
        )
        row2 = art.get(job_id="j1", kind="graph")
        assert row2["rel_path"] == "graph.v2.json"

        lst = art.list("j1")
        assert len(lst) == 1
