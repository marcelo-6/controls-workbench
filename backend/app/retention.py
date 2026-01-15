from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .core.settings import settings
from .run_storage import read_meta
from .storage import data_path

logger = logging.getLogger("api")


def _dir_size_bytes(p: Path) -> int:
    total = 0
    for fp in p.rglob("*"):
        if fp.is_file():
            total += fp.stat().st_size
    return total


def cleanup_uploads() -> int:
    uploads = data_path("uploads")
    if not uploads.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=settings.max_upload_age_hours)
    deleted = 0
    for d in uploads.iterdir():
        if not d.is_dir():
            continue
        mtime = datetime.fromtimestamp(d.stat().st_mtime, tz=UTC)
        if mtime < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            deleted += 1
    return deleted


def cleanup_runs() -> dict:
    runs_root = data_path("runs")
    runs_root.mkdir(parents=True, exist_ok=True)

    runs = []
    for d in runs_root.iterdir():
        if not d.is_dir():
            continue
        job_id = d.name
        meta = read_meta(job_id)
        if meta:
            created = meta.created_at
            accessed = meta.last_accessed_at
        else:
            st = d.stat()
            created = datetime.fromtimestamp(st.st_ctime, tz=UTC)
            accessed = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        size = _dir_size_bytes(d)
        runs.append((job_id, d, created, accessed, size))

    total_bytes = sum(r[4] for r in runs)
    total_count = len(runs)

    deleted = 0
    deleted_bytes = 0

    # LRU trim if over size/count
    if total_bytes > settings.max_runs_bytes or total_count > settings.max_runs_count:
        runs_sorted = sorted(runs, key=lambda x: x[3])  # last accessed asc
        for _job_id, d, _created, _accessed, size in runs_sorted:
            if total_bytes <= settings.max_runs_bytes and total_count <= settings.max_runs_count:
                break
            shutil.rmtree(d, ignore_errors=True)
            try:
                from .index_db import get_index_db

                get_index_db().delete_run(_job_id)
            except Exception:
                pass
            deleted += 1
            deleted_bytes += size
            total_bytes -= size
            total_count -= 1

    # TTL trim
    cutoff = datetime.now(UTC) - timedelta(days=settings.max_age_days)
    for _job_id, d, _created, _accessed, size in runs:
        if _created < cutoff and d.exists():
            shutil.rmtree(d, ignore_errors=True)
            try:
                from .index_db import get_index_db

                get_index_db().delete_run(_job_id)
            except Exception:
                pass
            deleted += 1
            deleted_bytes += size

    return {
        "deleted_runs": deleted,
        "deleted_bytes": deleted_bytes,
        "remaining_runs": total_count,
        "remaining_bytes": total_bytes,
    }
