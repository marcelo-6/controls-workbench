# backend/app/core/logging.py
"""
Application logging configuration and file-based log retention primitives.

This module provides the shared logging setup for Controls Workbench. It focuses on
producing logs that are:

- **Predictable**: consistent formatting and log levels across the backend.
- **Operationally friendly**: size-based rotation to cap disk usage.
- **Retention-aware**: rotated logs are gzip-compressed to reduce storage footprint.
- **Frontend-compatible**: stable on-disk filenames enable simple “tail” and “download”
  endpoints without special indexing or external log services.

Key concepts
------------
- The **root logger** is configured once via `configure_logging()` to establish a
  baseline console handler and formatting.
- Named loggers are created via `get_logger()` which attaches a rotating file handler
  that compresses older rotated files (e.g., `api.log.1.gz`, `api.log.2.gz`).

Important note
--------------
This module intentionally does **not** implement time-based deletion of log files.
Log retention is enforced through:
- maximum log file size (`settings.log_max_bytes`)
- maximum number of rotated backups (`settings.log_backup_count`)
- gzip compression of rotated backups

Any broader retention strategy (e.g., deleting logs older than N days) should be
implemented separately in a maintenance/retention component, not here.
"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.settings import settings


class GZipRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that compresses rotated log files with gzip.

    Rationale:
        - Keeps disk usage predictable (rotation) while preserving history.
        - Compresses rotated logs automatically, which helps retention goals.
        - Produces stable filenames the frontend can reference when listing/downloading logs.

    Behavior:
        - Writes active log to `baseFilename` (e.g., api.log).
        - On rollover, creates numbered files (api.log.1, api.log.2, ...).
        - Immediately gzips numbered files (api.log.1.gz, api.log.2.gz, ...) and removes
          the uncompressed originals.
    """

    def doRollover(self) -> None:
        super().doRollover()

        # Compress older rotated files (api.log.1, api.log.2, ...) -> .gz
        for i in range(1, settings.log_backup_count + 1):
            fn = f"{self.baseFilename}.{i}"
            gz = f"{fn}.gz"
            if os.path.exists(fn) and not os.path.exists(gz):
                with open(fn, "rb") as f_in, gzip.open(gz, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(fn)


def configure_logging() -> None:
    """
    Configure root logging defaults for the application.

    This sets up a consistent baseline format and log level across the app, while
    allowing named loggers (e.g., "api") to attach file handlers for persistence.

    Notes:
        - We keep the root logger simple; file handlers are created via `get_logger()`.
        - Avoid adding handlers multiple times (idempotent).

    Intended usage:
        Call once at app startup, before creating other loggers.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    root.addHandler(stream)


def get_logger(name: str, logfile: str | Path) -> logging.Logger:
    """
    Create or return a named logger configured with a rotating, gzip-compressing file handler.

    This logger is suitable for:
    - Tail endpoints (reading the active log file for recent lines).
    - Download endpoints (serving the active log file or older .gz files).
    - Predictable retention behavior via size-based rotation + limited backups.

    Args:
        name: Logger name (e.g., "api", "worker", "tools.ignition").
        logfile: Path to the active log file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    path = Path(logfile)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    handler = GZipRotatingFileHandler(
        filename=str(path),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d) - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S%z",
    )
    handler.setFormatter(formatter)

    # Replace handlers to avoid duplicates during reload/dev
    logger.handlers.clear()
    logger.addHandler(handler)

    # Prevent double-logging through root handlers
    logger.propagate = False

    return logger
