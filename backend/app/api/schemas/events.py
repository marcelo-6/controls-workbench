# backend/app/api/schemas/events.py
"""
Events API schemas.

Events are the structured "console output" stream for a run.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EventLine(BaseModel):
    """A single event line emitted during tool execution."""

    ts: str
    level: str
    message: str
    kind: str | None = None
    payload: dict[str, Any] | None = None


class EventsPayload(BaseModel):
    """Response payload returned when tailing events."""

    lines: list[EventLine]
