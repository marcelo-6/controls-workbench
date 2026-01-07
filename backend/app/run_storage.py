from __future__ import annotations

from pathlib import Path

from .run_models import RunMeta, RunState, utcnow
from .storage import data_path


def run_dir(job_id: str) -> Path:
    return data_path(job_id)


def meta_path(job_id: str) -> Path:
    return run_dir(job_id) / "meta.json"


def state_path(job_id: str) -> Path:
    return run_dir(job_id) / "state.json"


def events_path(job_id: str) -> Path:
    return run_dir(job_id) / "events.log"


def write_meta(meta: RunMeta) -> None:
    p = meta_path(meta.job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(meta.model_dump_json(by_alias=True, indent=2), encoding="utf-8")


def read_meta(job_id: str) -> RunMeta | None:
    p = meta_path(job_id)
    if not p.exists():
        return None
    return RunMeta.model_validate_json(p.read_text(encoding="utf-8"))


def touch_meta_access(job_id: str) -> None:
    meta = read_meta(job_id)
    if not meta:
        return
    meta.last_accessed_at = utcnow()
    write_meta(meta)


def write_state(state: RunState) -> None:
    p = state_path(state.job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.model_dump_json(by_alias=True, indent=2), encoding="utf-8")


def read_state(job_id: str) -> RunState | None:
    p = state_path(job_id)
    if not p.exists():
        return None
    return RunState.model_validate_json(p.read_text(encoding="utf-8"))


def append_event(job_id: str, line: str) -> None:
    p = events_path(job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def tail_lines(p: Path, n: int) -> list[str]:
    if not p.exists():
        return []
    # Simple tail for small files (fine for v0.1)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-n:]
