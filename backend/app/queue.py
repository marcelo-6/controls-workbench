from __future__ import annotations

from .config import settings
from .storage import ensure_dirs

ensure_dirs()

try:
    # Huey exposes SqliteHuey in newer releases.
    from huey import SqliteHuey  # type: ignore
except Exception:  # pragma: no cover
    from huey.contrib.sqlitedb import SqliteHuey  # type: ignore

huey = SqliteHuey(filename=settings.huey_db, fsync=settings.huey_fsync)

# Ensure tasks are registered when the Huey instance is imported.
from . import tasks  # noqa: E402,F401
