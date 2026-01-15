"""
settings.py Application settings and project metadata.

This module is the single source of truth for runtime configuration in the backend.
It combines environment-driven configuration (via `pydantic-settings` v2) with
package metadata (name/description/version) read from `pyproject.toml`.

Key responsibilities:
- Define the `Settings` model for all configurable runtime values (auth, storage,
  retention, logging, queue/DB paths), primarily sourced from environment variables
  and optional `.env` files.
- Resolve project metadata from `pyproject.toml` (cached) so FastAPI can expose
  accurate OpenAPI/Swagger information (title/description/version) without manual
  duplication.
- Normalize and validate filesystem paths using `pathlib.Path`, ensuring required
  directories exist and falling back to a safe local `./data` directory when the
  configured `data_dir` is not writable.
- Provide a cached `get_settings()` accessor suitable for FastAPI dependency
  injection, and a convenience `settings` singleton for non-DI usage.

Design goals:
- Centralize configuration to avoid drift across modules.
- Keep configuration deterministic and test-friendly (easy overrides, no hidden
  side effects beyond directory creation).
- Minimize repeated I/O by caching `pyproject.toml` reads and `Settings` instances.
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_pyproject(start: Path) -> Path | None:
    """
    Walk up from `start` looking for pyproject.toml.
    Works in Docker (/app/pyproject.toml) and local dev (backend/pyproject.toml).
    """
    start = start.resolve()
    for p in (start, *start.parents):
        candidate = p / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def _read_pyproject_project() -> dict[str, Any]:
    """
    Cached read of [project] from pyproject.toml.
    """
    here = Path(__file__).resolve()
    pyproject = _find_pyproject(here)
    if not pyproject:
        return {}

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return {}

    project = data.get("project", {})
    return project if isinstance(project, dict) else {}


def _ensure_writable_dir(p: Path) -> Path:
    """
    Ensure directory exists and is writable. If not writable, fallback to ./data.
    Returns the final directory path.
    """
    try:
        p.mkdir(parents=True, exist_ok=True)
        if not os.access(str(p), os.W_OK):
            raise PermissionError(f"Data dir not writable: {p}")

        probe = p / ".write_test"
        probe.mkdir(parents=True, exist_ok=True)
        probe.rmdir()
        return p
    except Exception:
        fallback = Path("./data").resolve()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class Settings(BaseSettings):
    """
    Central app configuration.

    - Uses pydantic-settings (env-driven)
    - Reads pyproject.toml for project metadata (name/description/version)
    - Normalizes derived paths under data_dir
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        env_file=(".env",),
        env_file_encoding="utf-8",
        validate_default=True,
    )

    # ---- Auth ----
    app_password: str = Field(default="change-me", description="Simple shared password for the UI.")
    secret_key: str = Field(default="change-me-too", description="Session signing secret.")

    # ---- Storage ----
    data_dir: Path = Field(
        default=Path("./data"), description="Root folder for all persisted app data."
    )

    # ---- Retention ----
    max_age_days: int = Field(default=7)
    max_runs_bytes: int = Field(default=5 * 1024**3)  # 5 GiB
    max_runs_count: int = Field(default=200)
    max_upload_age_hours: int = Field(default=24)

    # ---- Logging ----
    log_max_bytes: int = Field(default=20 * 1024**2)  # 20 MiB
    log_backup_count: int = Field(default=5)

    # ---- Huey ----
    huey_db: Path | None = Field(
        default=None,
        description="SQLite file path for Huey storage. Defaults under data_dir/queue/queue.db",
    )
    huey_fsync: bool = Field(default=False)

    # ---- Index DB (run history + artifact index) ----
    index_db: Path | None = Field(
        default=None,
        description="SQLite file path for app index DB. Defaults under data_dir/index/workbench.db",
    )

    # ---- Derived / project metadata from pyproject.toml ----
    @computed_field  # type: ignore[misc]
    @property
    def project_name(self) -> str:
        project = _read_pyproject_project()
        return str(project.get("name") or "controls-workbench")

    @computed_field  # type: ignore[misc]
    @property
    def project_description(self) -> str:
        project = _read_pyproject_project()
        return str(project.get("description") or "Controls Workbench")

    @computed_field  # type: ignore[misc]
    @property
    def backend_version(self) -> str:
        project = _read_pyproject_project()
        return str(project.get("version") or "0.0.0")

    # ---- Commonly used derived directories ----
    @computed_field  # type: ignore[misc]
    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @computed_field  # type: ignore[misc]
    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @computed_field  # type: ignore[misc]
    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @model_validator(mode="after")
    def _finalize_paths(self) -> Settings:
        # Normalize / ensure writable data_dir with fallback
        dd = _ensure_writable_dir(Path(self.data_dir))
        object.__setattr__(self, "data_dir", dd)

        # Fill derived DB paths if not provided
        huey_db = Path(self.huey_db) if self.huey_db is not None else (dd / "queue" / "queue.db")
        index_db = (
            Path(self.index_db) if self.index_db is not None else (dd / "index" / "workbench.db")
        )

        # Ensure parents exist
        huey_db.parent.mkdir(parents=True, exist_ok=True)
        index_db.parent.mkdir(parents=True, exist_ok=True)

        # Also ensure base dirs exist
        (dd / "uploads").mkdir(parents=True, exist_ok=True)
        (dd / "runs").mkdir(parents=True, exist_ok=True)
        (dd / "logs").mkdir(parents=True, exist_ok=True)

        object.__setattr__(self, "huey_db", huey_db)
        object.__setattr__(self, "index_db", index_db)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Convenience singleton (fine for scripts; for FastAPI deps, prefer get_settings()).
settings = get_settings()
