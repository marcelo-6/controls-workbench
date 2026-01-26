# Ignition Project Explorer — Analysis Layer

This package performs **analysis** over a parsed Ignition project export (`ProjectExport`)
to produce:

- `GraphBundle`:
  - `graph_full`: full dependency graph for offline/debugging and deeper analysis
  - `graph_ui`: filtered graph intended for default UI loading
  - `tree`: Designer-like tree where every resource leaf maps to a stable `node_id`
  - `stats`: lightweight summary metrics
- `ArtifactToWrite[]`:
  - per-node “source” artifacts (view.json, scripts, SQL, resource.json, config.json, thumbnails)
  - emitted deterministically to support fast frontend rendering

## Why "analysis" instead of "indexing"?

"Indexing" implies persistence/DB concerns or search indexing. This layer is purely:
- **model construction** (nodes/edges/tree)
- **reference resolution** (best-effort, confidence-scored)
- **artifact derivation** (per-node source payloads)
- **metrics** (counts and future quality signals)

No DB writes. No filesystem writes.

## Inputs / Outputs

### Input
- `zip_file: ZipFile`: opened archive for reading
- `export: ProjectExport`: manifest-driven resource list from `parser.py`
- `profile: dict | None`: optional UI filtering preferences

### Output
- `(GraphBundle, artifacts_to_write)`

## File layout & responsibilities

- `bundle.py`
  - orchestration entrypoint `build_graph_bundle(...)`
  - calls node creation, artifact creation, edge discovery, tree building, UI filtering, stats

- `ids.py`
  - stable ID helpers for nodes/edges/tree to keep everything deterministic

- `nodes.py`
  - convert parser `Resource` -> `GraphNode`
  - build normalized path index for reference resolution

- `artifacts.py`
  - emit per-node source artifacts from resource files (manifest order preserved)
  - avoid overwriting multiple scripts/sql files; also emits compatibility aliases

- `edges.py`
  - scan text-bearing files for references
  - special handling for Perspective view.json (embedded view paths + style classes)

- `resolver.py`
  - resolve references to:
    - existing nodes (exact and suffix match)
    - ambiguous derived nodes (multiple candidates)
    - missing derived nodes (no candidates)
  - confidence scoring lives here

- `tree.py`
  - build Designer-like tree using section order constants
  - leaf nodes always carry `node_id` so frontend can pan/zoom/highlight

- `profile.py`
  - normalize/validate `profile` settings used for `graph_ui` filtering

- `metrics.py`
  - compute counts & summary stats (extensible)

## Determinism guarantees

- Resource discovery ordering is handled by the parser (sorted by section/path/resource.json path).
- Node IDs are `uuid5` stable (type + normalized path).
- Edges are `uuid5` stable (src + tgt + edge_type + evidence/raw).
- Tree folder IDs are `uuid5` stable (section + folder path).
- Artifact emission order respects:
  1) resource.json
  2) manifest file list in manifest order
  3) optional data.bin last
  and uses stable naming for multi-file resources.

## Extension points

- Add new edge extraction rules:
  - implement in `edges.py` and/or `resolver.py`
  - keep confidence scoring explicit

- Add new output graph formats (e.g., eCharts):
  - implement a parallel renderer that consumes `Graph` and emits additional artifacts
  - do not contaminate the core node/edge model

- Add metrics:
  - extend `metrics.compute_stats(...)`

## Compatibility

`indexing.py` remains as a shim re-exporting:
- `ArtifactToWrite`
- `build_graph_bundle`

so existing imports like `from .indexing import build_graph_bundle` can remain unchanged.
