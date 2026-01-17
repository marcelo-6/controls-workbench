# backend/tests/unit/infra/queue/test_tasks.py
"""
Unit tests for Huey task adapters.

These tests ensure Huey tasks remain thin adapters that delegate to the proper
domain service entrypoints.

The test patches the service constructor path so no real database or tool logic
is required.
"""

from __future__ import annotations

from types import SimpleNamespace


def test_run_job_delegates_to_tools_service(monkeypatch) -> None:
    """
    `run_job(job_id)` should construct ToolsService and call `run_job(job_id=...)`.
    """
    called = {"job_id": None}

    class FakeToolsService:
        def __init__(self, **_kwargs):
            pass

        def run_job(self, *, job_id: str) -> None:
            called["job_id"] = job_id

    # Patch settings
    monkeypatch.setattr(
        "app.core.settings.get_settings",
        lambda: SimpleNamespace(db_path=":memory:", index_db="", huey_db="", huey_fsync=""),
    )

    # Patch db_session context manager
    class DummyConn:
        pass

    class DummyCtx:
        def __enter__(self):
            return DummyConn()

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr("app.infra.db.db.db_session", lambda _p: DummyCtx())
    monkeypatch.setattr("app.domain.tools.service.ToolsService", FakeToolsService)
    monkeypatch.setattr("app.domain.tools.registry.build_tools_registry", lambda: object())
    monkeypatch.setattr("app.infra.db.repos.jobs.JobsRepo", lambda _c: object())
    monkeypatch.setattr("app.infra.db.repos.uploads.UploadsRepo", lambda _c: object())
    monkeypatch.setattr("app.infra.db.repos.events.EventsRepo", lambda _c: object())
    monkeypatch.setattr("app.infra.db.repos.artifacts.ArtifactsRepo", lambda _c: object())

    from app.infra.queue.tasks import run_job

    run_job.call_local("job-xyz")
    assert called["job_id"] == "job-xyz"
