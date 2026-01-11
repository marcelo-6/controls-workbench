from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import settings

"""SQLite catalog for run history + parsed graph metadata.

This is intentionally separate from Huey's SQLite queue DB.
The goal is to make the UI fast (tree/search/subgraph) without re-reading
large JSON artifacts from disk.
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@dataclass(frozen=True)
class RunRow:
    job_id: str
    tool_id: str
    status: str
    created_at: datetime | None
    last_accessed_at: datetime | None
    parse_seconds: float | None
    nodes: int | None
    edges: int | None


class IndexDB:
    """Tiny repository wrapper around sqlite3."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init_schema(self) -> None:
        con = self._connect()
        try:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  job_id TEXT PRIMARY KEY,
                  tool_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT,
                  last_accessed_at TEXT,
                  parse_seconds REAL,
                  nodes INTEGER,
                  edges INTEGER,
                  meta_json TEXT
                );

                CREATE TABLE IF NOT EXISTS elements (
                  job_id TEXT NOT NULL,
                  element_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  type TEXT NOT NULL,
                  label TEXT NOT NULL,
                  path TEXT NOT NULL,
                  name TEXT,
                  source_file TEXT,
                  thumbnail_path TEXT,
                  metrics_json TEXT,
                  node_json TEXT NOT NULL,
                  PRIMARY KEY (job_id, element_id),
                  FOREIGN KEY(job_id) REFERENCES runs(job_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_elements_job_kind ON elements(job_id, kind);
                CREATE INDEX IF NOT EXISTS idx_elements_job_path ON elements(job_id, path);

                CREATE TABLE IF NOT EXISTS edges (
                  job_id TEXT NOT NULL,
                  edge_id TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  target_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  confidence TEXT,
                  evidence TEXT,
                  edge_json TEXT NOT NULL,
                  PRIMARY KEY(job_id, edge_id),
                  FOREIGN KEY(job_id) REFERENCES runs(job_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_edges_job_source ON edges(job_id, source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_job_target ON edges(job_id, target_id);

                CREATE TABLE IF NOT EXISTS trees (
                  job_id TEXT PRIMARY KEY,
                  tree_json TEXT NOT NULL,
                  FOREIGN KEY(job_id) REFERENCES runs(job_id) ON DELETE CASCADE
                );
                """
            )

            # Optional: FTS for search. If unavailable, we fall back to LIKE.
            try:
                con.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS fts_elements USING fts5(
                      job_id,
                      element_id,
                      kind,
                      label,
                      path,
                      name
                    );
                    """
                )
            except Exception:
                # ignore; some sqlite builds may not ship with fts5
                pass

            con.commit()
        finally:
            con.close()

    # ---------------------- runs ----------------------

    def upsert_run(
        self,
        *,
        job_id: str,
        tool_id: str,
        status: str,
        created_at: datetime | None = None,
        last_accessed_at: datetime | None = None,
        parse_seconds: float | None = None,
        nodes: int | None = None,
        edges: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO runs(job_id, tool_id, status, created_at, last_accessed_at,
                                parse_seconds, nodes, edges, meta_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                  tool_id=excluded.tool_id,
                  status=excluded.status,
                  created_at=COALESCE(excluded.created_at, runs.created_at),
                  last_accessed_at=COALESCE(excluded.last_accessed_at, runs.last_accessed_at),
                  parse_seconds=COALESCE(excluded.parse_seconds, runs.parse_seconds),
                  nodes=COALESCE(excluded.nodes, runs.nodes),
                  edges=COALESCE(excluded.edges, runs.edges),
                  meta_json=COALESCE(excluded.meta_json, runs.meta_json);
                """,
                (
                    job_id,
                    tool_id,
                    status,
                    _iso(created_at),
                    _iso(last_accessed_at),
                    parse_seconds,
                    nodes,
                    edges,
                    json.dumps(meta) if meta is not None else None,
                ),
            )
            con.commit()
        finally:
            con.close()

    def touch_run_access(self, job_id: str, last_accessed_at: datetime) -> None:
        con = self._connect()
        try:
            con.execute(
                "UPDATE runs SET last_accessed_at=? WHERE job_id=?",
                (_iso(last_accessed_at), job_id),
            )
            con.commit()
        finally:
            con.close()

    def list_recent_runs(self, limit: int) -> list[RunRow]:
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT job_id, tool_id, status, created_at, last_accessed_at, parse_seconds, nodes, edges
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                RunRow(
                    job_id=r["job_id"],
                    tool_id=r["tool_id"],
                    status=r["status"],
                    created_at=_parse_iso(r["created_at"]),
                    last_accessed_at=_parse_iso(r["last_accessed_at"]),
                    parse_seconds=r["parse_seconds"],
                    nodes=r["nodes"],
                    edges=r["edges"],
                )
                for r in rows
            ]
        finally:
            con.close()

    # ------------------- graph index -------------------

    def replace_graph(
        self,
        *,
        job_id: str,
        elements: Iterable[dict[str, Any]],
        edges: Iterable[dict[str, Any]],
        tree: dict[str, Any],
    ) -> None:
        """Replace all indexed graph data for a run."""

        con = self._connect()
        try:
            con.execute("DELETE FROM elements WHERE job_id=?", (job_id,))
            con.execute("DELETE FROM edges WHERE job_id=?", (job_id,))
            con.execute("DELETE FROM trees WHERE job_id=?", (job_id,))

            con.executemany(
                """
                INSERT INTO elements(
                  job_id, element_id, kind, type, label, path, name,
                  source_file, thumbnail_path, metrics_json, node_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        job_id,
                        e["element_id"],
                        e["kind"],
                        e["type"],
                        e["label"],
                        e["path"],
                        e.get("name"),
                        e.get("source_file"),
                        e.get("thumbnail_path"),
                        json.dumps(e.get("metrics", {})),
                        json.dumps(e["node_json"]),
                    )
                    for e in elements
                ],
            )

            con.executemany(
                """
                INSERT INTO edges(
                  job_id, edge_id, source_id, target_id, kind, confidence, evidence, edge_json
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        job_id,
                        ed["edge_id"],
                        ed["source_id"],
                        ed["target_id"],
                        ed["kind"],
                        ed.get("confidence"),
                        ed.get("evidence"),
                        json.dumps(ed["edge_json"]),
                    )
                    for ed in edges
                ],
            )

            con.execute(
                "INSERT INTO trees(job_id, tree_json) VALUES(?,?)",
                (job_id, json.dumps(tree)),
            )

            # refresh FTS
            try:
                con.execute("DELETE FROM fts_elements WHERE job_id=?", (job_id,))
                con.executemany(
                    "INSERT INTO fts_elements(job_id, element_id, kind, label, path, name) VALUES(?,?,?,?,?,?)",
                    [
                        (
                            job_id,
                            e["element_id"],
                            e["kind"],
                            e["label"],
                            e["path"],
                            e.get("name"),
                        )
                        for e in elements
                    ],
                )
            except Exception:
                pass

            con.commit()
        finally:
            con.close()

    def get_tree(self, job_id: str) -> dict[str, Any] | None:
        con = self._connect()
        try:
            row = con.execute("SELECT tree_json FROM trees WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                return None
            return json.loads(row["tree_json"])
        finally:
            con.close()

    def get_node_json(self, job_id: str, element_id: str) -> dict[str, Any] | None:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT node_json FROM elements WHERE job_id=? AND element_id=?",
                (job_id, element_id),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["node_json"])
        finally:
            con.close()

    def get_edges_for_node(self, job_id: str, element_id: str) -> tuple[list[dict], list[dict]]:
        con = self._connect()
        try:
            inbound = con.execute(
                "SELECT edge_json FROM edges WHERE job_id=? AND target_id=?",
                (job_id, element_id),
            ).fetchall()
            outbound = con.execute(
                "SELECT edge_json FROM edges WHERE job_id=? AND source_id=?",
                (job_id, element_id),
            ).fetchall()
            return (
                [json.loads(r["edge_json"]) for r in inbound],
                [json.loads(r["edge_json"]) for r in outbound],
            )
        finally:
            con.close()

    def search(self, job_id: str, q: str, limit: int = 50) -> list[dict[str, Any]]:
        q = (q or "").strip()
        if not q:
            return []
        con = self._connect()
        try:
            # Prefer FTS if available.
            try:
                rows = con.execute(
                    """
                    SELECT e.node_json
                    FROM fts_elements f
                    JOIN elements e
                      ON e.job_id=f.job_id AND e.element_id=f.element_id
                    WHERE f.job_id=? AND fts_elements MATCH ?
                    LIMIT ?
                    """,
                    (job_id, q, limit),
                ).fetchall()
                return [json.loads(r["node_json"]) for r in rows]
            except Exception:
                pass

            like = f"%{q}%"
            rows = con.execute(
                """
                SELECT node_json
                FROM elements
                WHERE job_id=? AND (path LIKE ? OR label LIKE ? OR name LIKE ?)
                ORDER BY kind, path
                LIMIT ?
                """,
                (job_id, like, like, like, limit),
            ).fetchall()
            return [json.loads(r["node_json"]) for r in rows]
        finally:
            con.close()

    def subgraph(
        self,
        *,
        job_id: str,
        roots: list[str],
        depth: int,
        direction: str = "both",
        max_nodes: int = 800,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (nodes, edges) for a BFS slice."""

        roots = [r for r in roots if r]
        if not roots:
            return ([], [])
        depth = max(0, min(depth, 10))
        max_nodes = max(10, min(max_nodes, 5000))
        direction = direction.lower()
        if direction not in {"out", "in", "both"}:
            direction = "both"

        con = self._connect()
        try:
            seen: set[str] = set(roots)
            frontier = set(roots)
            all_edges: list[dict[str, Any]] = []

            for _ in range(depth):
                if not frontier or len(seen) >= max_nodes:
                    break

                next_frontier: set[str] = set()

                if direction in {"out", "both"}:
                    rows = con.execute(
                        f"SELECT edge_json FROM edges WHERE job_id=? AND source_id IN ({','.join(['?'] * len(frontier))})",
                        (job_id, *frontier),
                    ).fetchall()
                    for r in rows:
                        ed = json.loads(r["edge_json"])
                        all_edges.append(ed)
                        tgt = ed.get("target")
                        if tgt and tgt not in seen and len(seen) < max_nodes:
                            seen.add(tgt)
                            next_frontier.add(tgt)

                if direction in {"in", "both"}:
                    rows = con.execute(
                        f"SELECT edge_json FROM edges WHERE job_id=? AND target_id IN ({','.join(['?'] * len(frontier))})",
                        (job_id, *frontier),
                    ).fetchall()
                    for r in rows:
                        ed = json.loads(r["edge_json"])
                        all_edges.append(ed)
                        src = ed.get("source")
                        if src and src not in seen and len(seen) < max_nodes:
                            seen.add(src)
                            next_frontier.add(src)

                frontier = next_frontier

            # fetch nodes
            if not seen:
                return ([], [])
            rows = con.execute(
                f"SELECT node_json FROM elements WHERE job_id=? AND element_id IN ({','.join(['?'] * len(seen))})",
                (job_id, *seen),
            ).fetchall()
            nodes = [json.loads(r["node_json"]) for r in rows]

            # de-dupe edges by id
            dedup_edges: dict[str, dict[str, Any]] = {}
            for ed in all_edges:
                eid = ed.get("id")
                if eid and eid not in dedup_edges:
                    dedup_edges[eid] = ed

            # Keep only edges where both endpoints are in the node set
            node_set = {n.get("id") for n in nodes}
            edges_out = [
                ed
                for ed in dedup_edges.values()
                if ed.get("source") in node_set and ed.get("target") in node_set
            ]
            return (nodes, edges_out)
        finally:
            con.close()

    def delete_run(self, job_id: str) -> int:
        with self._connect() as con:
            cur = con.execute("DELETE FROM runs WHERE job_id = ?", (job_id,))
            con.commit()
            return cur.rowcount

    def clear_runs(self) -> int:
        with self._connect() as con:
            cur = con.execute("DELETE FROM runs")
            con.commit()
            return cur.rowcount


@lru_cache(maxsize=1)
def get_index_db() -> IndexDB:
    return IndexDB(Path(settings.index_db))
