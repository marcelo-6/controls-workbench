# backend/app/infra/db/repos/events.py
"""
Job events repository.

Events are the backend's “tail-able” log lines for the UI polling experience.
This repo supports:
- append event
- tail last N events (returned oldest→newest for display)

Events are stored as TEXT timestamps (UTC ISO) to keep them JSON-safe and
SQLite-friendly.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.errors import DBError


class EventsRepo:
    """SQL access layer for the `job_events` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(
        self,
        *,
        job_id: str,
        ts: str,
        level: str,
        message: str,
        kind: str | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> None:
        """Append a new event row for a job."""
        try:
            payload_text = (
                json.dumps(payload_json, separators=(",", ":"), sort_keys=True)
                if payload_json is not None
                else None
            )
            self._conn.execute(
                """
                INSERT INTO job_events (job_id, ts, level, kind, message, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, ts, level, kind, message, payload_text),
            )
        except Exception as e:
            raise DBError(
                code="DB_INSERT_EVENT_FAILED",
                detail=f"Failed to append event for job {job_id}: {e}",
            ) from e

    def tail(self, *, job_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        """
        Return the newest events (limited), in chronological display order.

        Query is newest-first for efficiency, then reversed for UI rendering.
        """
        rows = self._conn.execute(
            """
            SELECT id, job_id, ts, level, kind, message, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in reversed(rows):
            d = dict(r)
            # Optional: decode payload_json back to dict for callers.
            # If your API expects a dict, uncomment this.
            if d.get("payload_json"):
                try:
                    d["payload_json"] = json.loads(d["payload_json"])
                except Exception:
                    pass
            out.append(d)
        return out
