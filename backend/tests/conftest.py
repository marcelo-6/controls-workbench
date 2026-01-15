# backend/tests/conftest.py
"""
Pytest configuration for the Controls Workbench backend.

This file provides:
- Import path normalization so the `app` package is importable regardless of how
  tests are executed (Makefile, IDE runner, CI, etc.).
- A filesystem isolation fixture that redirects the application's `DATA_DIR` to
  a temporary directory for each test, ensuring tests are hermetic and do not
  read/write real user data.
- Cache management for settings accessors that may be decorated with `lru_cache`.

Design notes:
- The backend intentionally uses filesystem blob storage for uploads and job
  artifacts. Tests must always use `tmp_path` to avoid modifying real files.
- If `get_settings()` is cached, tests must clear that cache after overriding
  environment variables so the new values take effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure `backend/` is on sys.path so `import app.*` works consistently.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture()
def isolated_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """
    Force the application to use a temporary DATA_DIR for the duration of a test.

    This fixture:
    - Sets the `DATA_DIR` environment variable to a temp folder.
    - Clears any cached `get_settings()` result (if present) so the new env var
      is picked up.
    - Returns the resolved DATA_DIR path so tests can assert on it.

    Args:
        monkeypatch: Pytest monkeypatch fixture for environment mutation.
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path: The temporary data directory used by the application during the test.
    """
    data_dir = (tmp_path / "data").resolve()
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    # Clear settings cache if the project uses @lru_cache for settings construction.
    try:
        from app.core.settings import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        # If settings module isn't available yet or does not expose a cache, ignore.
        pass

    return data_dir
