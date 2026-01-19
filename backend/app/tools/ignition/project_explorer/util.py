# backend/app/tools/ignition/project_explorer/util.py
"""
Ignition Project Explorer utility helpers.

This module provides small, test-friendly helpers used across parsing/indexing:

- Stable opaque IDs (UUID5) for nodes/edges.
- Safe path normalization for Ignition-style resource paths.
- Simple heuristics for resolving references (exact / partial / ambiguous).
- Small regex extractors used for dependency discovery in text/json blobs.

Important:
These utilities are intentionally free of filesystem writes and FastAPI imports.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# A fixed namespace UUID to ensure stable UUID5 generation across environments.
_NAMESPACE = uuid.UUID("2d8e3a9f-2e4e-4c08-a0bf-7b91b8bb0c34")


def stable_uuid5(*parts: str) -> str:
    """
    Generate a stable UUID5 string based on the provided parts.

    Args:
        *parts: Strings to combine into an ID seed.

    Returns:
        str: UUID string.
    """
    seed = "|".join(p.strip() for p in parts if p is not None)
    return str(uuid.uuid5(_NAMESPACE, seed))


def normalize_ignition_path(p: str | None) -> str:
    """
    Normalize an Ignition resource path for matching.

    Normalization rules:
    - strip whitespace
    - convert backslashes to forward slashes
    - remove leading/trailing slashes
    - collapse repeated slashes

    Args:
        p: Path-like string.

    Returns:
        str: Normalized path (may be empty).
    """
    if not p:
        return ""
    s = p.strip().replace("\\", "/")
    s = re.sub(r"/{2,}", "/", s)
    return s.strip("/")


def safe_json_dumps(obj: Any) -> str:
    """
    Dump an object as compact JSON, best-effort.

    Args:
        obj: JSON-serializable object.

    Returns:
        str: JSON string.
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def try_parse_json(raw: bytes) -> Any | None:
    """
    Attempt to parse JSON bytes.

    Args:
        raw: Raw bytes.

    Returns:
        Parsed JSON value, or None on failure.
    """
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


# -------------------------
# Dependency extraction
# -------------------------

# Perspective view path usage often appears as "Exchange/Dash/Dash" (no leading slash).
_VIEW_PATH_RE = re.compile(r'["\']([A-Za-z0-9 _.-]+(?:/[A-Za-z0-9 _.-]+){1,})["\']')

# Named query paths often appear in runNamedQuery("Folder/Query") or runNamedQuery(project, "Folder/Query")
_NAMED_QUERY_RE = re.compile(r"runNamedQuery\(\s*(?:[^,]+,\s*)?['\"]([^'\"]+)['\"]\s*\)")

# Style class "classes" field: space-separated class names (Designer stores a single string)
# We'll extract tokens that look like a/b/c (no spaces).
_STYLE_CLASS_TOKEN_RE = re.compile(r"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)")

# Generic tag-ish patterns (best-effort; v1 is intentionally conservative).
_TAG_BRACKET_RE = re.compile(r"(\[[^\]]+\][A-Za-z0-9_./-]+)")


@dataclass(frozen=True)
class ReferenceHit:
    """
    A reference hit extracted from text.

    Attributes:
        kind: Reference domain (e.g. "view", "named_query", "style_class", "tag").
        raw: Raw extracted string.
    """

    kind: str
    raw: str


def extract_references_from_text(text: str) -> list[ReferenceHit]:
    """
    Extract best-effort references from a text blob.

    This is intentionally heuristic and designed to be improved incrementally.

    Args:
        text: Input text.

    Returns:
        list[ReferenceHit]: Extracted reference hits.
    """
    hits: list[ReferenceHit] = []

    for m in _NAMED_QUERY_RE.finditer(text):
        hits.append(ReferenceHit(kind="named_query", raw=m.group(1)))

    for m in _TAG_BRACKET_RE.finditer(text):
        hits.append(ReferenceHit(kind="tag", raw=m.group(1)))

    # For view paths we require at least one slash to avoid matching common strings.
    for m in _VIEW_PATH_RE.finditer(text):
        candidate = m.group(1)
        if "/" in candidate:
            hits.append(ReferenceHit(kind="view", raw=candidate))

    return hits


def extract_style_classes(classes_value: str) -> list[str]:
    """
    Extract style class tokens from a Perspective 'style.classes' string.

    Args:
        classes_value: The raw "classes" string from view.json.

    Returns:
        list[str]: Individual class names.
    """
    if not classes_value:
        return []
    # The field is typically "a/b/c d/e/f"
    tokens = []
    for tok in classes_value.split():
        tok = tok.strip()
        if not tok:
            continue
        m = _STYLE_CLASS_TOKEN_RE.fullmatch(tok)
        if m:
            tokens.append(tok)
    return tokens


def best_effort_suffix_candidates(needle: str, candidates: Iterable[str]) -> list[str]:
    """
    Return candidates that match `needle` by suffix path segments.

    Example:
        needle="Exchange/Dash/Dash"
        candidate="perspective/views/Exchange/Dash/Dash"

    Args:
        needle: Normalized path reference.
        candidates: Candidate normalized paths.

    Returns:
        list[str]: Matching candidates.
    """
    n = normalize_ignition_path(needle)
    if not n:
        return []
    out: list[str] = []
    for c in candidates:
        cc = normalize_ignition_path(c)
        if not cc:
            continue
        if cc == n or cc.endswith("/" + n):
            out.append(c)
    return out
