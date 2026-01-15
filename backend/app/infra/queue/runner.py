# backend/app/infra/queue/runner.py
"""
Queue runner abstraction.

This module provides a single function (`enqueue_job`) used by domain services to
schedule background work.

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

from app.core.settings import get_settings


def enqueue_job(job_id: str) -> None:
    """
    Enqueue a job for execution.

    Args:
        job_id: Job identifier to run.

    Raises:
        RuntimeError: If the configured queue mode is not recognized.
    """
    s = get_settings()

    if s.huey_queue_mode == "sync":
        # Sync mode is intentionally a direct call to the Huey task function,
        # which resolves services and runs the domain logic.
        from app.infra.queue.tasks import run_job

        run_job(job_id)
        return

    if s.huey_queue_mode == "huey":
        from app.infra.queue.tasks import run_job

        run_job.delay(job_id)
        return

    raise RuntimeError(f"Unknown queue_mode: {s.huey_queue_mode}")
