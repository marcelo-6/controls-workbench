# backend/app/infra/queue/runner.py
"""
Queue runner abstraction.

This module provides a small indirection layer so domain services can request
background work without knowing whether execution is asynchronous (Huey) or
synchronous (tests/dev).

Why this exists:
- Production uses Huey `.delay(...)` to enqueue.
- Unit tests (and some integration tests) run jobs synchronously for deterministic
  execution without a worker process.

Configuration:
- `Settings.queue_mode` controls behavior:
    - "huey": enqueue asynchronously via Huey
    - "sync": execute immediately in-process
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings


@dataclass(frozen=True)
class QueueRunner:
    """
    Queue runner implementation selected by configuration.

    Attributes:
        mode: Queue mode string ("huey" or "sync").
    """

    mode: str

    def enqueue_job(self, job_id: str) -> None:
        """
        Enqueue a job for execution.

        In "sync" mode, the job executes immediately in-process.
        In "huey" mode, the job is enqueued for a Huey worker.

        Args:
            job_id: Job identifier to run.

        Raises:
            RuntimeError: If the configured queue mode is not recognized.
        """
        if self.mode == "sync":
            from app.infra.queue.tasks import run_job

            run_job(job_id)
            return

        if self.mode == "huey":
            from app.infra.queue.tasks import run_job

            run_job.delay(job_id)
            return

        raise RuntimeError(f"Unknown queue_mode: {self.mode}")


def build_queue_runner(settings: Settings) -> QueueRunner:
    """
    Build a queue runner from application settings.

    This factory keeps queue configuration and selection logic in one place and
    enables clean dependency injection into domain services.

    Args:
        settings: Application settings.

    Returns:
        QueueRunner: Runner configured for the requested queue mode.
    """
    return QueueRunner(mode=settings.huey_queue_mode)
