# backend/app/core/time.py
"""
Time utilities used across the backend.

This module centralizes time-related helpers to ensure consistent handling of
time zones and serialization throughout the application.

Design principles:
- Always use timezone-aware UTC timestamps for persisted state and API metadata.
- Keep helpers small, deterministic, and easy to mock/patch in tests.
- Avoid ad-hoc `datetime.now()` calls scattered across the codebase.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """
    Return the current timezone-aware UTC timestamp.

    This should be the default timestamp source for:
    - database rows (`created_at`, `started_at`, `finished_at`, etc.)
    - API metadata (`timestamp_utc`)
    - event logs / audit entries

    Returns:
        datetime: A timezone-aware datetime in UTC.
    """
    return datetime.now(UTC)
