# backend/app/infra/queue/huey_app.py
"""
Huey application configuration.

This module builds the Huey instance used for background execution of jobs.

Design goals:
- Keep configuration centralized and driven by `Settings`.
- Use Huey's SQLite storage backend for a simple, self-contained deployment.
- Avoid importing FastAPI or domain services here (queue is infrastructure).

Notes:
- The Huey consumer (worker) is started as a separate process/container.
- In unit tests, the project uses a sync runner (see `runner.py`) rather than
  relying on Huey's consumer.
"""

from __future__ import annotations

from huey import SqliteHuey

from app.core.settings import get_settings


def get_huey() -> SqliteHuey:
    """
    Construct and return a configured Huey instance.

    Returns:
        SqliteHuey: Huey instance configured with SQLite storage.
    """
    s = get_settings()
    return SqliteHuey(
        name="workbench",
        filename=str(s.huey_db),
        fsync=s.huey_fsync,
    )
