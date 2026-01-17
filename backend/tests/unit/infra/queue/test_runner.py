# backend/tests/unit/infra/queue/test_runner.py
"""
Unit tests for the queue runner abstraction.

These tests validate that:
- sync mode runs the job immediately (direct call)
- huey mode schedules via `.delay(job_id)`
- an unknown mode fails fast with a clear error
- the builder constructs a runner from settings

Implementation detail:
`QueueRunner.enqueue_job()` imports `run_job` lazily from `app.infra.queue.tasks`.
To keep these tests hermetic and avoid importing Huey or task wiring, we inject a
fake `app.infra.queue.tasks` module into `sys.modules`.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.infra.queue.runner import QueueRunner, build_queue_runner


def _install_fake_tasks_module(monkeypatch, run_job_obj) -> None:
    """
    Install a fake `app.infra.queue.tasks` module into `sys.modules`.

    This prevents importing the real task module (and any Huey wiring) while still
    allowing `from app.infra.queue.tasks import run_job` to resolve successfully.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        run_job_obj: Object to expose as `run_job`. For sync mode this should be a
            callable. For huey mode this should expose a `.delay(job_id)` method.
    """
    mod = ModuleType("app.infra.queue.tasks")
    mod.run_job = run_job_obj
    monkeypatch.setitem(sys.modules, "app.infra.queue.tasks", mod)


def test_queue_runner_sync_calls_task_immediately(monkeypatch) -> None:
    """
    In sync mode, `enqueue_job()` must execute the job immediately by calling the task
    function directly (not `.delay`).
    """
    called = {"job_id": None}

    def fake_run_job(job_id: str) -> None:
        called["job_id"] = job_id

    _install_fake_tasks_module(monkeypatch, fake_run_job)

    runner = QueueRunner(mode="sync")
    runner.enqueue_job("job-123")

    assert called["job_id"] == "job-123"


def test_queue_runner_huey_calls_delay(monkeypatch) -> None:
    """
    In huey mode, `enqueue_job()` must schedule work via `run_job.delay(job_id)`.
    """
    called = {"job_id": None}

    def fake_delay(job_id: str) -> None:
        called["job_id"] = job_id

    fake_task = SimpleNamespace(delay=fake_delay)
    _install_fake_tasks_module(monkeypatch, fake_task)

    runner = QueueRunner(mode="huey")
    runner.enqueue_job("job-456")

    assert called["job_id"] == "job-456"


def test_queue_runner_unknown_mode_raises() -> None:
    """
    An unknown queue mode should raise a clear RuntimeError to prevent silent
    misconfiguration.
    """
    runner = QueueRunner(mode="nope")

    with pytest.raises(RuntimeError, match="Unknown queue_mode"):
        runner.enqueue_job("job-789")


def test_build_queue_runner_uses_settings() -> None:
    """
    `build_queue_runner(settings)` should produce a QueueRunner configured from settings.

    This test uses a lightweight settings stub to avoid requiring a full Settings object.
    """
    settings_stub = SimpleNamespace(huey_queue_mode="sync")

    runner = build_queue_runner(settings_stub)

    assert isinstance(runner, QueueRunner)
    assert runner.mode == "sync"
