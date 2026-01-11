from __future__ import annotations

import tomllib
from pathlib import Path


def get_backend_version() -> str:
    """
    Read backend version from pyproject.toml.
    Assumes backend/app/* and backend/pyproject.toml live side-by-side (as in your repo).
    In Docker, this resolves to /app/pyproject.toml.
    """
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    try:
        data = tomllib.loads(pyproject.read_text())
    except Exception:
        data = {}
    return str(data.get("project", {}).get("version", "0.0.0"))
