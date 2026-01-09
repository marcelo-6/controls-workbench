from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import GraphDoc

"""Ignition graph indexing helpers.

This module turns the generated GraphDoc into:
 - an element table (typed nodes + small metadata)
 - an edge table (typed edges + confidence/evidence)
 - a Designer-like tree for UI selection

The goal is: parse once (in worker), query fast (in API) without re-reading
large JSON blobs.
"""


def _safe_join(*parts: str) -> str:
    return "/".join([p.strip("/") for p in parts if p and p.strip("/")])


def _thumbnail_rel_path(
    run_root: Path, extracted_root: Path, source_file: str | None
) -> str | None:
    """If a view folder has a thumbnail image, return path relative to run_root.

    We keep thumbnails on disk (from the extracted project export) and just store
    the relative path in SQLite so the frontend can request it via:
    /api/jobs/{job}/artifact?path=...
    """

    if not source_file:
        return None
    # source_file points to a file inside extracted_root, eg: .../view.json
    view_json = extracted_root / source_file
    if not view_json.exists():
        return None
    folder = view_json.parent
    for name in [
        "thumbnail.png",
        "thumbnail.jpg",
        "thumbnail.jpeg",
        "thumb.png",
        "thumb.jpg",
    ]:
        fp = folder / name
        if fp.exists() and fp.is_file():
            try:
                return fp.relative_to(run_root).as_posix()
            except Exception:
                # If it's not under run_root (shouldn't happen), don't expose it.
                return None
    return None


def _tree_insert(root: dict[str, Any], parts: list[str], leaf: dict[str, Any]) -> None:
    cur = root
    for part in parts:
        children = cur.setdefault("children", [])
        nxt = None
        for ch in children:
            if ch.get("label") == part and ch.get("kind") == "folder":
                nxt = ch
                break
        if nxt is None:
            nxt = {
                "id": _safe_join(cur.get("id", ""), part) or part,
                "label": part,
                "kind": "folder",
                "children": [],
            }
            children.append(nxt)
        cur = nxt
    cur.setdefault("children", []).append(leaf)


def build_index(
    *,
    run_root: Path,
    extracted_root: Path,
    graph: GraphDoc,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return (elements, edges, tree_json) to store in IndexDB."""

    # fan-in/out
    fan_in = Counter([e.target for e in graph.edges])
    fan_out = Counter([e.source for e in graph.edges])

    elements: list[dict[str, Any]] = []
    for n in graph.nodes:
        kind = str(n.data.get("kind") or n.type)
        source_file = n.data.get("source_file")

        metrics: dict[str, Any] = dict(n.data.get("metrics") or {})
        metrics.update({"fan_in": fan_in.get(n.id, 0), "fan_out": fan_out.get(n.id, 0)})

        thumb = None
        if kind == "perspective_view":
            thumb = _thumbnail_rel_path(run_root, extracted_root, source_file)

        node_json = n.model_dump(by_alias=True)
        # Make it easy for frontend (no extra DB query)
        node_json.setdefault("data", {})["metrics"] = metrics
        if thumb:
            node_json.setdefault("data", {})["thumbnail_path"] = thumb

        elements.append(
            {
                "element_id": n.id,
                "kind": kind,
                "type": n.type,
                "label": n.label,
                "path": n.path,
                "name": n.label,
                "source_file": source_file,
                "thumbnail_path": thumb,
                "metrics": metrics,
                "node_json": node_json,
            }
        )

    edges: list[dict[str, Any]] = []
    for e in graph.edges:
        edges.append(
            {
                "edge_id": e.id,
                "source_id": e.source,
                "target_id": e.target,
                "kind": e.type,
                "confidence": str(e.confidence),
                "evidence": e.evidence,
                "edge_json": e.model_dump(by_alias=True),
            }
        )

    # ---------------- tree model ----------------
    categories = {
        "Perspective Views": {"kinds": {"perspective_view"}, "id": "perspective"},
        "Scripts": {"kinds": {"python_script"}, "id": "scripts"},
        "Named Queries": {"kinds": {"named_query"}, "id": "queries"},
        "Tags": {"kinds": {"tag_path"}, "id": "tags"},
        "Missing": {"kinds": {"missing"}, "id": "missing"},
        "Other": {"kinds": set(), "id": "other"},
    }

    tree: dict[str, Any] = {
        "id": "root",
        "label": "Project",
        "kind": "root",
        "children": [],
    }

    # Prepare buckets
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for el in elements:
        k = el["kind"]
        cat_name = "Other"
        for name, cfg in categories.items():
            if cfg["kinds"] and k in cfg["kinds"]:
                cat_name = name
                break
        by_cat[cat_name].append(el)

    for cat_name, cfg in categories.items():
        items = by_cat.get(cat_name, [])
        if not items:
            continue
        cat_node = {
            "id": cfg["id"],
            "label": cat_name,
            "kind": "category",
            "children": [],
        }

        # Sort by path for stable ordering
        items.sort(key=lambda x: x.get("path") or "")
        for el in items:
            path = (el.get("path") or "").strip("/")
            parts = [p for p in path.split("/") if p]
            leaf = {
                "id": el["element_id"],
                "label": el["label"],
                "kind": el["kind"],
                "element_id": el["element_id"],
                "path": el["path"],
            }
            if el.get("thumbnail_path"):
                leaf["thumbnail_path"] = el["thumbnail_path"]
            # If there are folders, leaf name should be last part
            if parts:
                leaf["label"] = parts[-1]
                _tree_insert(cat_node, parts[:-1], leaf)
            else:
                cat_node.setdefault("children", []).append(leaf)

        tree["children"].append(cat_node)

    return elements, edges, tree
