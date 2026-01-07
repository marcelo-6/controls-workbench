from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Auth
    app_password: str = Field(default_factory=lambda: os.getenv("APP_PASSWORD", "change-me"))
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "change-me-too"))

    # Storage
    data_dir: str = Field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))

    # Retention
    max_age_days: int = Field(default_factory=lambda: int(os.getenv("MAX_AGE_DAYS", "7")))
    max_runs_bytes: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RUNS_BYTES", str(5 * 1024**3)))
    )
    max_runs_count: int = Field(default_factory=lambda: int(os.getenv("MAX_RUNS_COUNT", "200")))
    max_upload_age_hours: int = Field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_AGE_HOURS", "24"))
    )

    # Logging
    log_max_bytes: int = Field(
        default_factory=lambda: int(os.getenv("LOG_MAX_BYTES", str(20 * 1024**2)))
    )
    log_backup_count: int = Field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")))

    # Huey
    huey_db: str = Field(default_factory=lambda: os.getenv("HUEY_DB", "./data/queue/queue.db"))
    huey_fsync: bool = Field(
        default_factory=lambda: os.getenv("HUEY_FSYNC", "false").lower() == "true"
    )


settings = Settings()


# Normalize/fallback if not writable (common in local dev environments)
def _ensure_writable_data_dir() -> None:
    p = Path(settings.data_dir)
    try:
        p.mkdir(parents=True, exist_ok=True)
        # If dir exists but isn't writable, os.access will be False
        if not os.access(str(p), os.W_OK):
            raise PermissionError(f"Data dir not writable: {p}")
        # Also check we can create subfolders
        test = p / ".write_test"
        test.mkdir(parents=True, exist_ok=True)
        test.rmdir()
    except Exception:
        settings.data_dir = "./data"
        settings.huey_db = "./data/queue/queue.db"
        Path(settings.data_dir).mkdir(parents=True, exist_ok=True)


_ensure_writable_data_dir()
