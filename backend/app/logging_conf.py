from __future__ import annotations

import gzip
import logging
import os
import shutil
from logging.handlers import RotatingFileHandler

from .config import settings


class GZipRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        super().doRollover()

        # Compress older rotated files (e.g., api.log.1, api.log.2 ...)
        for i in range(1, settings.log_backup_count + 1):
            fn = f"{self.baseFilename}.{i}"
            gz = f"{fn}.gz"
            if os.path.exists(fn) and not os.path.exists(gz):
                with open(fn, "rb") as f_in, gzip.open(gz, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(fn)


def setup_logger(name: str, logfile: str) -> logging.Logger:
    os.makedirs(os.path.dirname(logfile), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = GZipRotatingFileHandler(
        logfile,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    handler.setFormatter(fmt)

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger
