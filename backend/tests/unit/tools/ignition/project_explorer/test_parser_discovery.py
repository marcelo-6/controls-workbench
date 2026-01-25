"""
Unit tests for Ignition project export parsing: manifest-driven resource discovery.

These tests focus strictly on:
- project selection (Designer export vs gateway backups)
- manifest scanning rules (resource.json is authoritative)
- manifest validation (JSON must be object, files must be list[str], all declared files exist)
- deterministic file ordering
- binary_only detection and data.bin handling
- attribute passthrough
- stable resource ordering by section/path/resource_json_path

Classification is tested separately in `test_project_explorer_parser_classification.py`.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from app.tools.ignition.project_explorer.parser import parse_project_export

# -------------------------
# ZIP builders (synthetic)
# -------------------------


def _zip_bytes(build_fn: Callable[[zipfile.ZipFile], None]) -> bytes:
    """
    Build a ZIP archive in-memory.

    Args:
        build_fn: Callback that writes ZIP entries using ZipFile.writestr.

    Returns:
        ZIP as raw bytes.
    """
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        build_fn(zf)
    return bio.getvalue()


def _parse(buf: bytes, project_root: str | None = None):
    """
    Parse a ZIP archive from bytes.

    Args:
        buf: ZIP bytes.
        project_root: Optional explicit root for gateway backups.

    Returns:
        ProjectExport.
    """
    with zipfile.ZipFile(io.BytesIO(buf), "r") as zf:
        return parse_project_export(zf, project_root=project_root)


def _write_json(zf: zipfile.ZipFile, path: str, obj) -> None:
    """
    Write JSON to a ZIP path.

    The parser reads JSON as UTF-8.
    """
    zf.writestr(path, json.dumps(obj, indent=2).encode("utf-8"))


def _write_bytes(zf: zipfile.ZipFile, path: str, data: bytes) -> None:
    """Write raw bytes to a ZIP path."""
    zf.writestr(path, data)


def _manifest(files: list[str] | None = None, *, attributes: dict | None = None):
    """
    Create a minimal Ignition resource.json manifest.

    Args:
        files: Manifest `files` list (default empty).
        attributes: Manifest `attributes` object.

    Returns:
        dict representing manifest JSON.
    """
    return {
        "scope": "G",
        "version": 1,
        "restricted": False,
        "overridable": True,
        "files": list(files or []),
        "attributes": attributes
        or {
            "lastModification": {
                "actor": "test",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        },
    }


def _add_resource(
    zf: zipfile.ZipFile,
    folder: str,
    files: list[str],
    *,
    payloads: dict[str, bytes] | None = None,
    manifest_attributes: dict | None = None,
) -> None:
    """
    Add a resource folder with resource.json and all declared files.

    Important:
        Ignition manifests list files by filename, e.g. "view.json", "data.bin".
        This helper writes them into the folder.

    Args:
        zf: ZipFile writer.
        folder: Folder path ending with '/'.
        files: Declared files in manifest (order matters).
        payloads: Optional override bytes per filename.
        manifest_attributes: Optional attributes object in resource.json.
    """
    assert folder.endswith("/"), "folder must end with '/'"
    payloads = payloads or {}

    _write_json(zf, folder + "resource.json", _manifest(files, attributes=manifest_attributes))
    for fname in files:
        _write_bytes(zf, folder + fname, payloads.get(fname, f"file:{fname}".encode()))


# -------------------------
# Project selection (strict)
# -------------------------


def test_designer_export_requires_project_json_at_root():
    """
    A single-project Designer export must have a project.json at the ZIP root.

    If absent, parsing must fail clearly, because we currently support exactly
    one project per Designer export ZIP.
    """
    buf = _zip_bytes(
        lambda zf: _add_resource(
            zf,
            "com.inductiveautomation.perspective/page-config/",
            ["config.json"],
            payloads={"config.json": b"{}"},
        )
    )

    with pytest.raises(ValueError, match=r"project\.json"):
        _parse(buf)


def test_designer_export_explicit_project_root_used_only_if_valid():
    """If project.json exists at root but caller provides project_root,
    parser uses it only if that folder also contains project.json."""

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "Root"})
        _write_json(zf, "alt/project.json", {"title": "Alt"})

    buf = _zip_bytes(build)

    # Valid override
    exp = _parse(buf, project_root="alt/")
    assert exp.project.project_root == "alt/"
    assert exp.project.title == "Alt"

    # Invalid override → fallback to root
    exp2 = _parse(buf, project_root="does_not_exist/")
    assert exp2.project.project_root == ""
    assert exp2.project.title == "Root"


def test_gateway_backup_explicit_project_root_missing_project_json_raises():
    """Explicit project_root provided but project.json missing → error."""

    def build(z):
        _write_json(z, "projects/A/project.json", {"title": "A"})

    buf = _zip_bytes(build)
    with pytest.raises(ValueError, match="project.json not found under selected"):
        _parse(buf, project_root="projects/B/")


def test_gateway_backup_no_project_json_anywhere_raises():
    """No project.json at root or under projects/* → error."""

    def build(z):
        _add_resource(z, "ignition/script-python/test/", ["code.py"])

    buf = _zip_bytes(build)
    with pytest.raises(ValueError, match="project.json not found"):
        _parse(buf)


def test_read_project_json_non_dict_raises():
    """project.json must decode to a dict."""

    def build(z):
        _write_json(z, "project.json", ["not", "a", "dict"])

    buf = _zip_bytes(build)
    with pytest.raises(ValueError, match="not valid JSON object"):
        _parse(buf)


def test_gateway_backup_autoselects_when_exactly_one_project_present():
    """
    For gateway backups (multi-project archive format), if exactly one project
    exists under projects/<name>/project.json (or Projects/...), the parser
    should auto-select it.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "projects/Only/project.json", {"title": "Only"})
        _add_resource(
            zf,
            "projects/Only/com.inductiveautomation.perspective/page-config/",
            ["config.json"],
            payloads={"config.json": b"{}"},
        )

    exp = _parse(_zip_bytes(build))
    assert exp.project.project_root in ("projects/Only/", "Projects/Only/")
    assert exp.project.title == "Only"


def test_gateway_backup_requires_explicit_root_when_multiple_projects_present():
    """
    For gateway backups that contain more than one project, parsing without
    project_root must fail clearly. The caller must select a specific project.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "projects/A/project.json", {"title": "A"})
        _write_json(zf, "projects/B/project.json", {"title": "B"})

        _add_resource(
            zf,
            "projects/A/com.inductiveautomation.perspective/page-config/",
            ["config.json"],
        )
        _add_resource(
            zf,
            "projects/B/com.inductiveautomation.perspective/page-config/",
            ["config.json"],
        )

    buf = _zip_bytes(build)
    with pytest.raises(ValueError, match=r"multiple projects"):
        _parse(buf)

    exp_a = _parse(buf, project_root="projects/A/")
    assert exp_a.project.project_root == "projects/A/"
    assert exp_a.project.title == "A"

    exp_b = _parse(buf, project_root="projects/B/")
    assert exp_b.project.project_root == "projects/B/"
    assert exp_b.project.title == "B"


# -------------------------
# Manifest-driven discovery
# -------------------------


def test_folders_without_resource_json_are_ignored():
    """
    Ensure folders lacking resource.json are NOT treated as resources.

    Even if they contain typical Ignition resource files (e.g. view.json),
    the parser must ignore them because resource.json is the authoritative
    signal that a folder is an Ignition resource.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _write_bytes(zf, "com.inductiveautomation.perspective/views/A/B/view.json", b"{}")
        _write_bytes(zf, "com.inductiveautomation.perspective/views/A/B/thumbnail.png", b"png")

    exp = _parse(_zip_bytes(build))
    assert list(exp.iter_resources()) == []


def test_resource_json_must_be_valid_json_object():
    """
    resource.json must parse as JSON and be a JSON object.

    - invalid JSON => ValueError
    - JSON but not an object (list/number/string) => ValueError
    """

    def build_invalid_json(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _write_bytes(
            zf,
            "com.inductiveautomation.perspective/page-config/resource.json",
            b"{not json",
        )
        _write_bytes(zf, "com.inductiveautomation.perspective/page-config/config.json", b"{}")

    with pytest.raises(ValueError, match=r"resource\.json"):
        _parse(_zip_bytes(build_invalid_json))

    def build_not_object(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _write_bytes(
            zf,
            "com.inductiveautomation.perspective/page-config/resource.json",
            b'["nope"]',
        )
        _write_bytes(zf, "com.inductiveautomation.perspective/page-config/config.json", b"{}")

    with pytest.raises(ValueError, match=r"not a JSON object"):
        _parse(_zip_bytes(build_not_object))


@pytest.mark.parametrize(
    "bad_files_value",
    [
        None,
        "config.json",
        123,
        {"x": "y"},
        ["config.json", 123],
    ],
)
def test_manifest_files_must_be_list_of_strings(bad_files_value):
    """
    The manifest 'files' property must be a list[str].

    Any other value must fail clearly because downstream logic depends on it
    for deterministic artifact ordering and file validation.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _write_json(
            zf,
            "com.inductiveautomation.perspective/page-config/resource.json",
            {
                "scope": "G",
                "version": 1,
                "files": bad_files_value,
            },
        )
        _write_bytes(zf, "com.inductiveautomation.perspective/page-config/config.json", b"{}")

    with pytest.raises(ValueError, match=r"Invalid resource\.json.*files"):
        _parse(_zip_bytes(build))


def test_manifest_declared_files_must_exist():
    """
    If resource.json declares files that are missing from the archive,
    the parser must raise a ValueError listing the missing paths.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        # Declares view.json but only thumbnail exists.
        _write_json(
            zf,
            "com.inductiveautomation.perspective/views/Exchange/Dash/Dash/resource.json",
            _manifest(["view.json", "thumbnail.png"]),
        )
        _write_bytes(
            zf,
            "com.inductiveautomation.perspective/views/Exchange/Dash/Dash/thumbnail.png",
            b"png",
        )

    with pytest.raises(ValueError, match=r"declares missing files"):
        _parse(_zip_bytes(build))


def test_manifest_filenames_must_not_include_path_separators():
    """
    Defensive validation: manifest file entries must be filenames, not paths.

    Real Ignition exports use filenames ("view.json", "data.bin"). If a manifest
    contains "subdir/file.txt", we treat it as invalid to avoid surprise traversal
    or mismatched expectations about folder structure.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _write_json(
            zf,
            "com.inductiveautomation.perspective/page-config/resource.json",
            _manifest(["../config.json"]),
        )
        # We intentionally do not write the declared file.

    with pytest.raises(ValueError, match=r"missing file"):
        _parse(_zip_bytes(build))


def test_file_order_is_resource_json_then_manifest_order_exact():
    """
    The parser must produce deterministic file ordering:

        [resource.json] + manifest files in exact order (kinds mapped)

    This is critical for stable front-end rendering and repeatable indexing.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _add_resource(
            zf,
            "com.inductiveautomation.perspective/views/A/View/",
            ["thumbnail.png", "view.json"],  # intentionally reversed
            payloads={"view.json": b"{}", "thumbnail.png": b"png"},
        )

    exp = _parse(_zip_bytes(build))
    r = exp.resources[0]
    assert [f.kind for f in r.files] == ["resource.json", "thumbnail", "view.json"]


def test_binary_only_true_when_data_bin_exists_even_if_not_declared():
    """
    Defensive behavior: if data.bin exists but is not declared in files, the
    parser should still set binary_only=True and include the file once at the end.

    This supports future variations or unusual exports.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        folder = "com.inductiveautomation.reporting/reports/Report/"
        _write_json(zf, folder + "resource.json", _manifest([]))
        _write_bytes(zf, folder + "data.bin", b"\x00\x01")

    exp = _parse(_zip_bytes(build))
    r = exp.resources[0]
    assert r.binary_only is True
    assert [f.kind for f in r.files] == ["resource.json", "data.bin"]


def test_manifest_attributes_are_copied_to_resource_attributes():
    """
    The parser must preserve manifest attributes, because UI/indexer will use
    lastModification metadata (actor/timestamp/signature) for display/audit hints.
    """
    attrs = {
        "lastModification": {"actor": "admin", "timestamp": "2026-01-18T10:52:08Z"},
        "enabled": True,
    }

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        _add_resource(
            zf,
            "com.inductiveautomation.perspective/message/toast-clearout/",
            ["handleMessage.py"],
            payloads={"handleMessage.py": b"pass"},
            manifest_attributes=attrs,
        )

    exp = _parse(_zip_bytes(build))
    r = exp.resources[0]
    assert r.attributes.get("enabled") is True
    assert r.attributes.get("lastModification", {}).get("actor") == "admin"


def test_resource_sort_order_is_stable():
    """
    The parser must sort resources deterministically by:
        (section, path, resource_json_path)

    This ensures repeatable output for the same archive regardless of ZIP write order.
    """

    def build(zf: zipfile.ZipFile):
        _write_json(zf, "project.json", {"title": "X"})
        # Add out-of-order to ensure parser sorting applies
        _add_resource(zf, "ignition/script-python/zeta/", ["code.py"])
        _add_resource(zf, "ignition/script-python/alpha/", ["code.py"])
        _add_resource(zf, "com.inductiveautomation.perspective/page-config/", ["config.json"])

    exp1 = _parse(_zip_bytes(build))
    exp2 = _parse(_zip_bytes(build))

    assert [r.resource_json_path for r in exp1.resources] == [
        r.resource_json_path for r in exp2.resources
    ]


# -------------------------
# Real-world fixture tests (optional, skipped if missing)
# -------------------------


@pytest.fixture(scope="session")
def ignition_fixtures_dir() -> Path | None:
    """
    Optional directory containing real Ignition exports.

    Conventions:
        tests/fixtures/ignition/*.zip
        tests/fixtures/ignition/*.gwbk

    """
    default = Path(__file__).resolve().parents[4] / "fixtures" / "ignition"
    return default if default.exists() and default.is_dir() else None


def _fixture_archives(fixtures_dir: Path) -> list[Path]:
    out: list[Path] = []
    out.extend(sorted(fixtures_dir.glob("*.zip")))
    out.extend(sorted(fixtures_dir.glob("*.gwbk")))
    return out


@pytest.mark.parametrize("archive_name", ["__AUTO__"])
def test_real_world_exports_manifest_integrity_and_determinism(ignition_fixtures_dir, archive_name):
    """
    Integration-style test: run discovery against real exports.

    This test validates:
    - every discovered resource has resource.json first
    - every resource file path exists in ZIP
    - no duplicated data.bin entries
    - stable ordering across two parses
    """
    if ignition_fixtures_dir is None:
        pytest.skip("No Ignition fixture exports directory found.")

    archives = _fixture_archives(ignition_fixtures_dir)

    if not archives:
        pytest.skip("No *.zip or *.gwbk fixture exports found.")

    for ap in archives:
        with zipfile.ZipFile(ap, "r") as zf:
            exp1 = parse_project_export(zf)  # auto-select if possible
        with zipfile.ZipFile(ap, "r") as zf:
            exp2 = parse_project_export(zf)

        assert [r.resource_json_path for r in exp1.resources] == [
            r.resource_json_path for r in exp2.resources
        ]

        # Basic integrity checks
        with zipfile.ZipFile(ap, "r") as zf:
            names = set(zf.namelist())

        for r in exp1.resources:
            assert r.files, f"Resource has no files: {r.resource_json_path}"
            assert r.files[0].kind == "resource.json"
            assert r.files[0].zip_path in names

            # Ensure every listed file exists
            for f in r.files:
                assert f.zip_path in names, f"Missing file referenced by parser: {f.zip_path}"
