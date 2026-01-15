# backend/app/infra/db/db.py
"""
SQLite bootstrap and connection management.

This module provides the minimal, test-friendly DB plumbing for Controls Workbench:

- `init_db()` applies `schema.sql` idempotently (v0 “no migrations” approach).
- `connect()` returns a configured `sqlite3.Connection` with sensible defaults.
- `db_session()` is a small context manager that commits on success and rolls
  back on exceptions.

Design rules:
- The DB is the source of truth for *queryable state* (jobs/uploads/events/artifacts).
- All timestamps are stored as UTC ISO-8601 strings (TEXT) per DB_SCHEMA.md.
- Repositories (in `infra/db/repos`) must use parameterized SQL only.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.errors import DBError

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def init_db(db_path: Path) -> None:
    """
    Initialize the SQLite database by applying the schema idempotently.

    Args:
        db_path: Full path to the sqlite database file.

    Raises:
        DBError: If the schema cannot be applied.
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        # with connect(db_path) as conn:
        #     conn.executescript(schema_sql)
        #     conn.commit()
        conn = connect(db_path)
        try:
            conn.executescript(schema_sql)
            conn.commit()
        finally:
            conn.close()

    except Exception as e:
        raise DBError(detail=f"Failed to initialize DB at {db_path}: {e}") from e


def connect(db_path: Path) -> sqlite3.Connection:
    """
    Open a configured SQLite connection.

    Notes:
    - `row_factory` is set to `sqlite3.Row` so repos can return dict-like rows.
    - Foreign keys are enforced.
    - WAL mode is enabled for better concurrent read/write behavior in dev/prod.

    Args:
        db_path: Full path to the sqlite database file.

    Returns:
        sqlite3.Connection: An open sqlite connection.
    """
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row

    # Keep pragmas close to the connection boundary.
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    return conn


@contextmanager
def db_session(db_path: Path) -> Iterator[sqlite3.Connection]:
    """
    Context manager for a unit-of-work DB session.

    - Commits on normal exit.
    - Rolls back on exception.
    - Always closes the connection.

    Args:
        db_path: Full path to the sqlite database file.

    Yields:
        sqlite3.Connection: An open sqlite connection.

    Raises:
        DBError: If commit/rollback fails unexpectedly.
    """
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise DBError(detail=f"DB session failed: {e}") from e
    finally:
        conn.close()
