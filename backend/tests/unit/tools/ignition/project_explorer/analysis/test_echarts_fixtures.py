"""
Integration tests: build ECharts artifacts from real Ignition exports.

These tests validate that:
- real Designer exports (*.zip) and Gateway backups (*.gwbk) can be parsed
- GraphBundle can be constructed
- ECharts artifacts are emitted and JSON is well-formed
- output is deterministic for a given input archive
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.tools.ignition.project_explorer.analysis import (
    build_graph_bundle,
)  # noqa: F401
from app.tools.ignition.project_explorer.analysis.echarts import emit_echarts_artifacts
from app.tools.ignition.project_explorer.parser import parse_project_export

FIXTURES_DIR = Path(__file__).resolve().parents[5] / "fixtures" / "ignition"


def _fixture_paths() -> list[Path]:
    zips = sorted(FIXTURES_DIR.glob("*.zip"))
    gwbks = sorted(FIXTURES_DIR.glob("*.gwbk"))
    return zips + gwbks


@pytest.mark.parametrize("archive_path", _fixture_paths(), ids=lambda p: p.name)
def test_echarts_artifacts_from_fixture_archive_are_valid_and_deterministic(
    archive_path: Path,
):
    """
    Parse + build bundle + emit ECharts artifacts for each real-world fixture.

    This is intentionally structural (not snapshot-bytes) because fixtures can evolve.
    The deterministic check ensures *within the same run* the output is stable.
    """
    assert archive_path.exists(), f"Fixture not found: {archive_path}"

    with zipfile.ZipFile(archive_path, "r") as z:
        export = parse_project_export(z, project_root=None)

        # Build the bundle using the current pipeline
        bundle, _artifacts = build_graph_bundle(zip_file=z, export=export, profile=None)

        arts1 = emit_echarts_artifacts(bundle)
        arts2 = emit_echarts_artifacts(bundle)

    # We expect exactly these artifacts always
    assert [a.kind for a in arts1] == [
        "echarts_graph_full",
        "echarts_graph_ui",
        "echarts_tree",
    ]

    # Deterministic bytes for same bundle
    assert [a.bytes_ for a in arts1] == [a.bytes_ for a in arts2]

    # Validate JSON shapes
    full = json.loads(arts1[0].bytes_.decode("utf-8"))
    ui = json.loads(arts1[1].bytes_.decode("utf-8"))
    tree = json.loads(arts1[2].bytes_.decode("utf-8"))

    assert set(full.keys()) == {"categories", "nodes", "links"}
    assert set(ui.keys()) == {"categories", "nodes", "links"}
    assert isinstance(full["nodes"], list)
    assert isinstance(full["links"], list)
    assert isinstance(full["categories"], list)

    # Tree must be a single root object with expected keys
    assert isinstance(tree, dict)
    assert "name" in tree and "kind" in tree
    assert tree["kind"] == "root"

    # Sanity: graph_full nodes should always be >= graph_ui nodes
    assert len(full["nodes"]) >= len(ui["nodes"])
