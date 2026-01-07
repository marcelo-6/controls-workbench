from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Confidence, GraphDoc, GraphEdge, GraphMeta, GraphNode

_VIEW_COMPONENT_TYPES = {"ia.display.view", "ia.display.embeddedView"}
_TAG_PATH_RE = re.compile(r"(\[[^\]]+\][A-Za-z0-9_./\-]+)")
# Very light view-path heuristic
_VIEW_PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)+$")


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def make_node_id(node_type: str, path: str) -> str:
    return _sha1(f"{node_type}:{path}")


def _rel_posix(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def derive_view_path(view_json: Path) -> str:
    parts = [x.lower() for x in view_json.parts]
    # Find the last occurrence of "views" and take everything after it up to view.json
    idxs = [i for i, x in enumerate(parts) if x == "views"]
    if idxs:
        i = idxs[-1]
        # view_json is .../views/<viewPath...>/view.json
        sub = view_json.parts[i + 1 : -1]  # exclude view.json itself
        return "/".join(sub)
    # Fallback: use parent folder name
    return view_json.parent.name


def derive_script_path(py_file: Path, root: Path) -> str:
    return _rel_posix(py_file, root)


def derive_query_path(q_file: Path, root: Path) -> str:
    # If a file is under a folder containing "named-query" or "namedqueries", derive the folder path
    rel = _rel_posix(q_file, root)
    return rel


def walk_json(obj: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    yield pointer, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_ptr = f"{pointer}/{k}" if pointer else f"/{k}"
            yield from walk_json(v, child_ptr)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child_ptr = f"{pointer}/{i}" if pointer else f"/{i}"
            yield from walk_json(v, child_ptr)


def extract_view_refs_from_view_json(view_obj: Any) -> list[tuple[str, Confidence, str]]:
    refs: list[tuple[str, Confidence, str]] = []

    # High confidence: embedded view components with props.path
    for ptr, obj in walk_json(view_obj):
        if isinstance(obj, dict) and "type" in obj and obj.get("type") in _VIEW_COMPONENT_TYPES:
            props = obj.get("props") if isinstance(obj.get("props"), dict) else {}
            cand = props.get("path") or props.get("viewPath") or props.get("view_path")
            if isinstance(cand, str) and cand.strip():
                refs.append((cand.strip(), Confidence.high, f"{ptr}/props/path"))
        # Medium: keys named viewPath
        if isinstance(obj, dict):
            for key in ("viewPath", "view_path"):
                cand = obj.get(key)
                if isinstance(cand, str) and cand.strip():
                    refs.append((cand.strip(), Confidence.medium, f"{ptr}/{key}"))

    # De-dupe preserving strongest confidence
    best: dict[str, tuple[Confidence, str]] = {}
    rank = {Confidence.high: 3, Confidence.medium: 2, Confidence.low: 1}
    for path, conf, ev in refs:
        if path not in best or rank[conf] > rank[best[path][0]]:
            best[path] = (conf, ev)

    return [(p, c, ev) for p, (c, ev) in best.items()]


def extract_tag_paths_from_any_json(view_obj: Any) -> list[tuple[str, Confidence, str]]:
    out: dict[str, tuple[Confidence, str]] = {}
    for ptr, obj in walk_json(view_obj):
        if isinstance(obj, str):
            for m in _TAG_PATH_RE.findall(obj):
                out[m] = (Confidence.low, ptr)
        if isinstance(obj, dict):
            for key in ("tagPath", "tag_path"):
                cand = obj.get(key)
                if isinstance(cand, str) and _TAG_PATH_RE.search(cand):
                    out[cand] = (Confidence.medium, f"{ptr}/{key}")
    return [(p, c, ev) for p, (c, ev) in out.items()]


def extract_refs_from_script(text: str) -> dict[str, list[tuple[str, Confidence, str]]]:
    refs: dict[str, list[tuple[str, Confidence, str]]] = {"views": [], "tags": [], "queries": []}

    # Views: system.perspective.openPopup("path") / navigate("path") / openView("path")
    view_patterns = [
        re.compile(
            r"system\.perspective\.(?:openPopup|navigate|openView)\(\s*[\"\']([^\"\']+)[\"\']"
        ),
    ]
    for pat in view_patterns:
        for m in pat.finditer(text):
            vp = m.group(1).strip()
            if vp and _VIEW_PATH_RE.match(vp):
                refs["views"].append((vp, Confidence.medium, f"script:{m.start()}"))

    # Tags: system.tag.readBlocking([...]) / writeBlocking([...])
    tag_list_pat = re.compile(
        r"system\.tag\.(?:readBlocking|writeBlocking)\(\s*\[(.*?)\]", re.DOTALL
    )
    str_pat = re.compile(r"[\"\']([^\"\']+)[\"\']")
    for m in tag_list_pat.finditer(text):
        inside = m.group(1)
        for sm in str_pat.finditer(inside):
            s = sm.group(1)
            if _TAG_PATH_RE.search(s):
                refs["tags"].append((s, Confidence.medium, f"script:{m.start()}"))

    # Named queries: system.db.runNamedQuery("QueryPath")
    q_pat = re.compile(r"system\.db\.runNamedQuery\(\s*[\"\']([^\"\']+)[\"\']")
    for m in q_pat.finditer(text):
        qp = m.group(1).strip()
        if qp:
            refs["queries"].append((qp, Confidence.medium, f"script:{m.start()}"))

    return refs


def compute_scc(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    # Tarjan SCC
    adj: dict[str, list[str]] = defaultdict(list)
    for s, t in edges:
        adj[s].append(t)

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    idx: dict[str, int] = {}
    low: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str):
        nonlocal index
        idx[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, []):
            if w not in idx:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], idx[w])

        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(comp)

    for v in nodes:
        if v not in idx:
            strongconnect(v)
    return sccs


def build_graph(root: Path, job_id: str) -> tuple[GraphDoc, dict, str]:
    t0 = time.time()

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node: GraphNode) -> None:
        nodes.setdefault(node.id, node)

    def add_missing_node(node_type: str, path: str) -> GraphNode:
        nid = make_node_id(node_type, path)
        if nid in nodes:
            return nodes[nid]
        n = GraphNode(
            id=nid,
            type="resource",
            label=f"[MISSING] {path}",
            path=path,
            data={"kind": "missing", "expected_type": node_type},
        )
        add_node(n)
        return n

    # -------- index views ----------
    view_files = list(root.rglob("view.json"))
    for vf in view_files:
        try:
            view_path = derive_view_path(vf)
            nid = make_node_id("view", view_path)
            add_node(
                GraphNode(
                    id=nid,
                    type="view",
                    label=view_path.split("/")[-1] if view_path else vf.parent.name,
                    path=view_path,
                    data={"kind": "perspective_view", "source_file": _rel_posix(vf, root)},
                )
            )
        except Exception:
            continue

    # -------- index scripts ----------
    script_files = [p for p in root.rglob("*.py") if p.is_file()]
    for sf in script_files:
        sp = derive_script_path(sf, root)
        nid = make_node_id("script", sp)
        add_node(
            GraphNode(
                id=nid,
                type="script",
                label=sf.stem,
                path=sp,
                data={
                    "kind": "python_script",
                    "source_file": sp,
                    "metrics": {"bytes": sf.stat().st_size},
                },
            )
        )

    # -------- index named queries (best effort) ----------
    # Heuristic: include .sql files and query.json files
    query_files = [
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".sql", ".json"} and "query" in p.name.lower()
    ]
    for qf in query_files:
        qp = derive_query_path(qf, root)
        nid = make_node_id("query", qp)
        add_node(
            GraphNode(
                id=nid,
                type="query",
                label=qf.stem,
                path=qp,
                data={
                    "kind": "named_query",
                    "source_file": qp,
                    "metrics": {"bytes": qf.stat().st_size},
                },
            )
        )

    # -------- extract references from views ----------
    for vf in view_files:
        try:
            vf_rel = _rel_posix(vf, root)
            vpath = derive_view_path(vf)
            src_id = make_node_id("view", vpath)
            if src_id not in nodes:
                continue

            obj = json.loads(vf.read_text(encoding="utf-8", errors="ignore"))

            # embedded view refs
            for ref_path, conf, ev in extract_view_refs_from_view_json(obj):
                tgt_id = make_node_id("view", ref_path)
                if tgt_id not in nodes:
                    add_missing_node("view", ref_path)
                edges.append(
                    GraphEdge(
                        id=make_node_id("edge", f"{src_id}->{tgt_id}:{ev}"),
                        source=src_id,
                        target=tgt_id,
                        type="embeds",
                        confidence=conf,
                        evidence=f"{vf_rel}:{ev}",
                    )
                )

            # tag paths
            for tag_path, conf, ev in extract_tag_paths_from_any_json(obj):
                tgt_id = make_node_id("tag", tag_path)
                if tgt_id not in nodes:
                    add_node(
                        GraphNode(
                            id=tgt_id,
                            type="tag",
                            label=tag_path.split("/")[-1],
                            path=tag_path,
                            data={"kind": "tag_path", "source_file": vf_rel},
                        )
                    )
                edges.append(
                    GraphEdge(
                        id=make_node_id("edge", f"{src_id}->{tgt_id}:{ev}"),
                        source=src_id,
                        target=tgt_id,
                        type="reads",
                        confidence=conf,
                        evidence=f"{vf_rel}:{ev}",
                    )
                )

        except Exception:
            continue

    # -------- extract references from scripts ----------
    for sf in script_files:
        try:
            sp = derive_script_path(sf, root)
            src_id = make_node_id("script", sp)
            if src_id not in nodes:
                continue

            txt = sf.read_text(encoding="utf-8", errors="ignore")
            refs = extract_refs_from_script(txt)

            for vp, conf, ev in refs["views"]:
                tgt_id = make_node_id("view", vp)
                if tgt_id not in nodes:
                    add_missing_node("view", vp)
                edges.append(
                    GraphEdge(
                        id=make_node_id("edge", f"{src_id}->{tgt_id}:{ev}"),
                        source=src_id,
                        target=tgt_id,
                        type="calls",
                        confidence=conf,
                        evidence=ev,
                    )
                )

            for tp, conf, ev in refs["tags"]:
                tgt_id = make_node_id("tag", tp)
                if tgt_id not in nodes:
                    add_node(
                        GraphNode(
                            id=tgt_id,
                            type="tag",
                            label=tp.split("/")[-1],
                            path=tp,
                            data={"kind": "tag_path"},
                        )
                    )
                edges.append(
                    GraphEdge(
                        id=make_node_id("edge", f"{src_id}->{tgt_id}:{ev}"),
                        source=src_id,
                        target=tgt_id,
                        type="reads",
                        confidence=conf,
                        evidence=ev,
                    )
                )

            for qp, conf, ev in refs["queries"]:
                tgt_id = make_node_id("query", qp)
                if tgt_id not in nodes:
                    add_missing_node("query", qp)
                edges.append(
                    GraphEdge(
                        id=make_node_id("edge", f"{src_id}->{tgt_id}:{ev}"),
                        source=src_id,
                        target=tgt_id,
                        type="calls",
                        confidence=conf,
                        evidence=ev,
                    )
                )

        except Exception:
            continue

    # -------- stats + issues ----------
    node_list = list(nodes.values())
    edge_list = edges

    counts_by_type = Counter([n.type for n in node_list])
    counts_by_edge_type = Counter([e.type for e in edge_list])

    inbound = Counter([e.target for e in edge_list])
    missing_ids = {n.id for n in node_list if n.data.get("kind") == "missing"}
    orphans = [n.id for n in node_list if n.id not in missing_ids and inbound.get(n.id, 0) == 0]

    # broken refs: edges into missing nodes
    broken_refs = []
    for e in edge_list:
        if e.target in missing_ids:
            broken_refs.append(
                {"source": e.source, "target": e.target, "type": e.type, "evidence": e.evidence}
            )

    # cycles (exclude missing nodes)
    core_nodes = [n.id for n in node_list if n.id not in missing_ids]
    core_edges = [
        (e.source, e.target) for e in edge_list if e.source in core_nodes and e.target in core_nodes
    ]
    sccs = compute_scc(core_nodes, core_edges)

    # top lists
    fan_in = inbound
    fan_out = Counter([e.source for e in edge_list])
    most_ref = [{"node_id": nid, "count": cnt} for nid, cnt in fan_in.most_common(20)]
    most_out = [{"node_id": nid, "count": cnt} for nid, cnt in fan_out.most_common(20)]

    dt = time.time() - t0

    meta = GraphMeta(
        job_id=job_id,
        stats={
            "parse_seconds": round(dt, 3),
            "counts_by_type": dict(counts_by_type),
            "counts_by_edge_type": dict(counts_by_edge_type),
            "nodes": len(node_list),
            "edges": len(edge_list),
        },
    )
    graph = GraphDoc(meta=meta, nodes=node_list, edges=edge_list)

    report = {
        "stats": {
            "nodes": len(node_list),
            "edges": len(edge_list),
            "counts_by_type": dict(counts_by_type),
            "counts_by_edge_type": dict(counts_by_edge_type),
        },
        "issues": {
            "orphans": orphans[:500],
            "broken_refs": broken_refs[:500],
            "cycles": sccs[:200],
        },
        "top_lists": {
            "most_referenced": most_ref,
            "highest_fanout": most_out,
        },
    }

    summary_md = f"""# Summary

- Job: `{job_id}`
- Tool: `ignition.graph`
- Created: {datetime.now(UTC).isoformat()}
- Parse seconds: {meta.stats.get("parse_seconds")}
- Nodes: {meta.stats.get("nodes")}
- Edges: {meta.stats.get("edges")}

## Counts by type

```json
{json.dumps(dict(counts_by_type), indent=2)}
```

## Issues (high level)

- Orphans (max 500 shown): {len(report["issues"]["orphans"])}
- Broken refs (max 500 shown): {len(report["issues"]["broken_refs"])}
- Cycles (max 200 shown): {len(report["issues"]["cycles"])}
"""

    return graph, report, summary_md
