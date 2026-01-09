from __future__ import annotations

import os
from pathlib import Path

from .config import settings


def data_path(*parts: str) -> Path:
    """Return a path under DATA_DIR as a pathlib.Path."""
    return Path(settings.data_dir, *parts)


def ensure_dirs() -> None:
    # Create core folders. If the configured DATA_DIR isn't writable, fall back to ./data.
    base = Path(settings.data_dir)
    try:
        base.mkdir(parents=True, exist_ok=True)
        if not os.access(str(base), os.W_OK):
            raise PermissionError(f"Data dir not writable: {base}")
    except Exception:
        settings.data_dir = "./data"
        settings.huey_db = "./data/queue/queue.db"
        base = Path(settings.data_dir)
        base.mkdir(parents=True, exist_ok=True)

    for p in ["uploads", "runs", "logs", "queue", "index"]:
        Path(data_path(p)).mkdir(parents=True, exist_ok=True)
