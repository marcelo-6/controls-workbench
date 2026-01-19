# backend/app/infra/queue/huey_app.py
"""
Huey application configuration.

This module defines the single Huey instance used by the worker process to
consume and execute background tasks.

Why a module-level instance is required:
- Huey's consumer bootstraps by importing a dotted path that must resolve to a
  Huey instance (e.g., `app.infra.queue.huey_app.huey`).
- Tasks must register on the *same* Huey instance that the consumer runs.

Design goals:
- Keep configuration centralized and driven by `Settings`.
- Use Huey's SQLite storage backend for a simple, self-contained deployment.
- Avoid importing FastAPI or domain services here (queue is infrastructure only).

Testing notes:
- Unit tests should not rely on the worker. They typically run jobs synchronously
  via `infra.queue.runner` in "sync" mode.
"""

from __future__ import annotations

from functools import lru_cache

from huey import SqliteHuey

from app.core.settings import get_settings


@lru_cache(maxsize=1)
def get_huey() -> SqliteHuey:
    """
    Construct (once) and return the configured Huey instance.

    The result is cached to guarantee that task registration and the consumer
    process reference the same Huey instance.

    Returns:
        SqliteHuey: Huey instance configured with SQLite storage.
    """
    s = get_settings()
    return SqliteHuey(
        name="workbench",
        filename=str(s.huey_db),
        fsync=s.huey_fsync,
    )


# IMPORTANT: Huey consumer imports this symbol by dotted path.
huey: SqliteHuey = get_huey()

# Import tasks so decorators execute and tasks are registered in Huey's registry.
# noqa avoids "imported but unused" noise.
from app.infra.queue import tasks as _tasks  # noqa: F401,E402
