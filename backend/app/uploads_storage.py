from __future__ import annotations

import hashlib
from pathlib import Path

from .storage import data_path


def upload_dir(upload_id: str) -> Path:
    return data_path("uploads", upload_id)


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_project_zip(upload_id: str) -> Path | None:
    d = upload_dir(upload_id)
    if not d.exists():
        return None
    for p in d.iterdir():
        if p.is_file() and p.suffix.lower() == ".zip":
            return p
    return None


def find_tags_json(upload_id: str) -> Path | None:
    d = upload_dir(upload_id)
    if not d.exists():
        return None
    for p in d.iterdir():
        if p.is_file() and p.suffix.lower() == ".json":
            return p
    return None
