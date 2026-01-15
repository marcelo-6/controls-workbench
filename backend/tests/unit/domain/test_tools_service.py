# backend/tests/unit/domain/test_tools_service.py
from __future__ import annotations

"""
Unit tests for ToolsService.

These tests validate the job state machine:
- successful tool run marks job success and indexes artifacts
- failing tool run marks job failed and persists error fields
"""

import json
from pathlib import Path

import pytest

from app.core.time import utcnow_iso
from app.domain.tools.registry import ToolSpec, ToolsRegistry
from app.domain.tools.service import ToolsService
from app.infra.db.db import db_session, init_db
from app.infra.db.repos.artifacts import ArtifactsRepo
from app.infra.db.repos.events import EventsRepo
from app.infra.db.repos.jobs import JobsRepo
from app.infra.db.repos.uploads import UploadsRepo
from app.infra.storage.artifacts_fs import read_artifact_bytes


def test_run_job_success_marks_success_and_writes_artifact(
    isolated_data_dir: Path,
) -> None:
    """
    On success, ToolsService must:
    - transition queued -> running -> success
    - emit lifecycle events
    - write an artifact to disk and upsert it into artifacts table
    """
    db_path = isolated_data_dir / "index.sqlite"
    init_db(db_path)

    registry = ToolsRegistry()

    def runner(ctx):
        ctx.emit_event(level="info", message="hello", kind="tool")
        ctx.write_artifact(
            kind="graph",
            rel_path="artifacts/graph.json",
            content_type="application/json",
            data=b'{"nodes":[],"edges":[]}',
            meta=json.dumps({"v": 1}),
        )

    registry.register(
        ToolSpec(tool_id="dummy.ok", name="Dummy OK", description="test"),
        runner,
    )

    with db_session(db_path) as conn:
        uploads = UploadsRepo(conn)
        jobs = JobsRepo(conn)
        events = EventsRepo(conn)
        artifacts = ArtifactsRepo(conn)

        now = utcnow_iso()
        uploads.create(
            upload_id="upl-ok",
            created_at=now,
            last_accessed_at=now,
            project_zip_path="project.zip",
            tags_json_path=None,
            size_bytes=1,
            sha256="abc",
        )
        jobs.create(
            job_id="job-ok",
            tool_id="dummy.ok",
            upload_id="upl-ok",
            created_at=now,
            last_accessed_at=now,
            status="queued",
            params_json="{}",
        )

        svc = ToolsService(
            registry=registry,
            jobs_repo=jobs,
            uploads_repo=uploads,
            events_repo=events,
            artifacts_repo=artifacts,
        )
        svc.run_job(job_id="job-ok")

        job = jobs.get("job-ok")
        assert job is not None
        assert job["status"] == "success"
        assert job["artifacts_ready"] == 1

        a = artifacts.get(job_id="job-ok", kind="graph")
        assert a is not None
        payload = read_artifact_bytes("job-ok", a["rel_path"])
        assert payload.startswith(b"{")

        tail = events.tail(job_id="job-ok", limit=200)
        assert any(e["message"].startswith("Tool started") for e in tail)
        assert any(e["message"].startswith("Tool finished") for e in tail)


def test_run_job_failure_marks_failed(isolated_data_dir: Path) -> None:
    """
    If the tool runner raises, ToolsService must:
    - mark the job as failed
    - store stable error fields
    - append an error lifecycle event
    """
    db_path = isolated_data_dir / "index.sqlite"
    init_db(db_path)

    registry = ToolsRegistry()

    def runner(_ctx):
        raise RuntimeError("boom")

    registry.register(
        ToolSpec(tool_id="dummy.fail", name="Dummy Fail", description="test"),
        runner,
    )

    with db_session(db_path) as conn:
        uploads = UploadsRepo(conn)
        jobs = JobsRepo(conn)
        events = EventsRepo(conn)
        artifacts = ArtifactsRepo(conn)

        now = utcnow_iso()
        uploads.create(
            upload_id="upl-fail",
            created_at=now,
            last_accessed_at=now,
            project_zip_path="project.zip",
            tags_json_path=None,
            size_bytes=1,
            sha256="abc",
        )
        jobs.create(
            job_id="job-fail",
            tool_id="dummy.fail",
            upload_id="upl-fail",
            created_at=now,
            last_accessed_at=now,
            status="queued",
            params_json="{}",
        )

        svc = ToolsService(
            registry=registry,
            jobs_repo=jobs,
            uploads_repo=uploads,
            events_repo=events,
            artifacts_repo=artifacts,
        )

        with pytest.raises(RuntimeError):
            svc.run_job(job_id="job-fail")

        job = jobs.get("job-fail")
        assert job is not None
        assert job["status"] == "failed"
        assert job["error_code"] == "tool_failed"
        assert "boom" in (job["error_message"] or "")

        tail = events.tail(job_id="job-fail", limit=200)
        assert any(e["level"] == "error" for e in tail)
