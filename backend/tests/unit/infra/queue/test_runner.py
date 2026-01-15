# backend/tests/unit/infra/queue/test_runner.py
"""
Unit tests for the queue runner abstraction.

These tests validate that:
- sync mode runs the job immediately
- huey mode schedules via `.delay`
- an unknown mode fails fast with a clear error

No Huey worker is required for these tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_enqueue_job_sync_calls_task_immediately(monkeypatch) -> None:
    """
    In sync mode, `enqueue_job` must execute the job immediately by calling the task
    function directly (not `.delay`).
    """
    called = {"job_id": None}

    def fake_get_settings():
        return SimpleNamespace(huey_queue_mode="sync")

    def fake_run_job(job_id: str) -> None:
        called["job_id"] = job_id

    # Patch settings and task import targets
    monkeypatch.setattr("app.infra.queue.runner.get_settings", fake_get_settings)
    monkeypatch.setattr("app.infra.queue.tasks.run_job", fake_run_job)

    from app.infra.queue.runner import enqueue_job

    enqueue_job("job-123")
    assert called["job_id"] == "job-123"


def test_enqueue_job_huey_calls_delay(monkeypatch) -> None:
    """
    In huey mode, `enqueue_job` must schedule work via `run_job.delay(job_id)`.
    """
    called = {"job_id": None}

    def fake_get_settings():
        return SimpleNamespace(huey_queue_mode="huey")

    def fake_delay(job_id: str) -> None:
        called["job_id"] = job_id

    fake_task = SimpleNamespace(delay=fake_delay)

    monkeypatch.setattr("app.infra.queue.runner.get_settings", fake_get_settings)
    monkeypatch.setattr("app.infra.queue.tasks.run_job", fake_task)

    from app.infra.queue.runner import enqueue_job

    enqueue_job("job-456")
    assert called["job_id"] == "job-456"


def test_enqueue_job_unknown_mode_raises(monkeypatch) -> None:
    """
    An unknown queue mode should raise a clear RuntimeError to prevent silent
    misconfiguration.
    """

    def fake_get_settings():
        return SimpleNamespace(huey_queue_mode="nope")

    monkeypatch.setattr("app.infra.queue.runner.get_settings", fake_get_settings)

    from app.infra.queue.runner import enqueue_job

    with pytest.raises(RuntimeError, match="Unknown queue_mode"):
        enqueue_job("job-789")
