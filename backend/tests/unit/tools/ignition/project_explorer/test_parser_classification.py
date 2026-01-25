# backend/tests/unit/tools/ignition/project_explorer/test_parser_classifier.py
"""
Unit tests for resource classification in the Ignition project export parser.

These tests validate that for a given resource.json path (root-relative),
the parser produces:
- correct type_key
- correct section
- correct logical path

Resource discovery is tested separately.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.tools.ignition.project_explorer.constants import (
    SECTION_ALARM_PIPELINES,
    SECTION_EVENT_STREAMS,
    SECTION_NAMED_QUERIES,
    SECTION_PERSPECTIVE,
    SECTION_PROPERTIES,
    SECTION_REPORTS,
    SECTION_SCRIPTS,
    SECTION_SFC,
    TYPE_ALARM_PIPELINE,
    TYPE_EVENT_STREAM,
    TYPE_NAMED_QUERY,
    TYPE_PERSPECTIVE_MESSAGE_HANDLER,
    TYPE_PERSPECTIVE_PAGE_CONFIG,
    TYPE_PERSPECTIVE_STYLE_CLASS,
    TYPE_PERSPECTIVE_STYLESHEET,
    TYPE_PERSPECTIVE_VIEW,
    TYPE_PROJECT_PROPERTIES,
    TYPE_REPORT,
    TYPE_SCRIPT_GATEWAY_EVENT,
    TYPE_SCRIPT_PYTHON,
    TYPE_SFC,
)
from app.tools.ignition.project_explorer.parser import parse_project_export


def _manifest(files):
    return {"scope": "G", "version": 1, "files": list(files), "attributes": {}}


def _zip_bytes(build_fn):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        build_fn(zf)
    return bio.getvalue()


def _write_json(zf: zipfile.ZipFile, path: str, obj) -> None:
    zf.writestr(path, json.dumps(obj, indent=2).encode("utf-8"))


def _write_bytes(zf: zipfile.ZipFile, path: str, data: bytes) -> None:
    zf.writestr(path, data)


def _add_resource(zf: zipfile.ZipFile, folder: str, files: list[str]):
    assert folder.endswith("/")
    _write_json(zf, folder + "resource.json", _manifest(files))
    for f in files:
        _write_bytes(zf, folder + f, f"file:{f}".encode())


@pytest.mark.parametrize(
    "folder, files, expected_type, expected_section, expected_path",
    [
        # Perspective view
        (
            "com.inductiveautomation.perspective/views/Exchange/Dash/Dash/",
            ["view.json", "thumbnail.png"],
            TYPE_PERSPECTIVE_VIEW,
            SECTION_PERSPECTIVE,
            "Exchange/Dash/Dash",
        ),
        # Perspective page config
        (
            "com.inductiveautomation.perspective/page-config/",
            ["config.json"],
            TYPE_PERSPECTIVE_PAGE_CONFIG,
            SECTION_PERSPECTIVE,
            "page-config",
        ),
        # Perspective style class
        (
            "com.inductiveautomation.perspective/style-classes/exchange/toast/demo/button/clear/",
            ["style.json"],
            TYPE_PERSPECTIVE_STYLE_CLASS,
            SECTION_PERSPECTIVE,
            "exchange/toast/demo/button/clear",
        ),
        # Perspective stylesheet
        (
            "com.inductiveautomation.perspective/stylesheet/",
            ["stylesheet.css"],
            TYPE_PERSPECTIVE_STYLESHEET,
            SECTION_PERSPECTIVE,
            "stylesheet",
        ),
        # Perspective message handler
        (
            "com.inductiveautomation.perspective/message/toast-clearout/",
            ["handleMessage.py"],
            TYPE_PERSPECTIVE_MESSAGE_HANDLER,
            SECTION_PERSPECTIVE,
            "message/toast-clearout",
        ),
        # Alarm pipeline (binary-only typical)
        (
            "com.inductiveautomation.alarm-notification/alarm-pipelines/New Folder/New Pipeline/",
            ["data.bin"],
            TYPE_ALARM_PIPELINE,
            SECTION_ALARM_PIPELINES,
            "New Folder/New Pipeline",
        ),
        # Event stream
        (
            "com.inductiveautomation.eventstream/event-streams/New Folder/Event Stream - http/",
            ["config.json"],
            TYPE_EVENT_STREAM,
            SECTION_EVENT_STREAMS,
            "New Folder/Event Stream - http",
        ),
        # Report
        (
            "com.inductiveautomation.reporting/reports/Report/",
            ["data.bin"],
            TYPE_REPORT,
            SECTION_REPORTS,
            "Report",
        ),
        # SFC chart
        (
            "com.inductiveautomation.sfc/charts/New Chart/",
            ["sfc.xml"],
            TYPE_SFC,
            SECTION_SFC,
            "New Chart",
        ),
        # Project library script
        (
            "ignition/script-python/exchange/toast/demo/",
            ["code.py"],
            TYPE_SCRIPT_PYTHON,
            SECTION_SCRIPTS,
            "exchange/toast/demo",
        ),
        # Gateway event script (startup)
        (
            "ignition/startup/",
            ["onStartup.py"],
            TYPE_SCRIPT_GATEWAY_EVENT,
            SECTION_SCRIPTS,
            "startup",
        ),
        # Named query
        (
            "ignition/named-query/New Folder/Query/",
            ["query.sql"],
            TYPE_NAMED_QUERY,
            SECTION_NAMED_QUERIES,
            "New Folder/Query",
        ),
        # Global props -> project_properties
        (
            "ignition/global-props/",
            ["data.bin"],
            TYPE_PROJECT_PROPERTIES,
            SECTION_PROPERTIES,
            "global-props",
        ),
    ],
)
def test_classification_for_known_resource_families(
    folder, files, expected_type, expected_section, expected_path
):
    """
    Validate classification by resource location.

    Each case creates exactly one resource folder with resource.json + manifest files,
    parses it, and asserts the parser's classification result matches expectations.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _add_resource(zf, folder, files)

    buf = _zip_bytes(build)
    with zipfile.ZipFile(io.BytesIO(buf), "r") as zf:
        exp = parse_project_export(zf)

    assert len(exp.resources) == 1
    r = exp.resources[0]
    assert r.type_key == expected_type
    assert r.section == expected_section
    assert r.path == expected_path


def test_thumbnail_kind_mapping_is_applied():
    """
    Confirm that thumbnail files declared in the manifest map to kind='thumbnail'.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _add_resource(
            zf,
            "com.inductiveautomation.perspective/views/A/View/",
            ["view.json", "thumbnail.jpeg"],
        )

    buf = _zip_bytes(build)
    with zipfile.ZipFile(io.BytesIO(buf), "r") as zf:
        exp = parse_project_export(zf)

    r = exp.resources[0]
    kinds = [f.kind for f in r.files]
    assert kinds == ["resource.json", "view.json", "thumbnail"]
