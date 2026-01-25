# backend/app/tools/ignition/project_explorer/parser.py
"""
Ignition project export / gateway backup parser (manifest-driven).

Core rule:
- A "resource" is any folder containing a `resource.json`.
- `resource.json.files` is the source of truth for the resource's files.
- Folders without `resource.json` are just folders (not resources).

Supported inputs:
- Designer export ZIP: `project.json` at ZIP root
- Gateway backup (or similar): `projects/<name>/project.json` (or `Projects/<name>/project.json`)
  - If multiple projects exist, caller must specify `project_root`.

The parser performs no filesystem writes and no DB access.
"""

from __future__ import annotations

import json
import zipfile
from typing import Any

from .constants import (
    PFX_ALARM_PIPELINES,
    PFX_EVENT_STREAMS,
    PFX_IGNITION_GLOBAL_PROPS,
    PFX_IGNITION_MESSAGE,
    PFX_IGNITION_NAMED_QUERY,
    PFX_IGNITION_SCHEDULED,
    PFX_IGNITION_SCRIPT_PYTHON,
    PFX_IGNITION_SHUTDOWN,
    PFX_IGNITION_STARTUP,
    PFX_IGNITION_TAG_CHANGE,
    PFX_IGNITION_TIMER,
    PFX_IGNITION_UPDATE,
    PFX_PERSPECTIVE_ACCELEROMETER,
    PFX_PERSPECTIVE_AUTH_CHALLENGE,
    PFX_PERSPECTIVE_BARCODE,
    PFX_PERSPECTIVE_BLUETOOTH,
    PFX_PERSPECTIVE_FORM_SUBMISSION,
    PFX_PERSPECTIVE_KEY_EVENT,
    PFX_PERSPECTIVE_MESSAGE,
    PFX_PERSPECTIVE_NFC_SCAN,
    PFX_PERSPECTIVE_PAGE_CONFIG,
    PFX_PERSPECTIVE_PAGE_STARTUP,
    PFX_PERSPECTIVE_SESSION_PROPS,
    PFX_PERSPECTIVE_SHUTDOWN,
    PFX_PERSPECTIVE_STARTUP,
    PFX_PERSPECTIVE_STYLE_CLASSES,
    PFX_PERSPECTIVE_STYLESHEET,
    PFX_PERSPECTIVE_VIEWS,
    PFX_REPORTS,
    PFX_SFC,
    PROJECTS_DIR_CANDIDATES,
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
    TYPE_PERSPECTIVE_ACCELEROMETER,
    TYPE_PERSPECTIVE_AUTH_CHALLENGE,
    TYPE_PERSPECTIVE_BARCODE,
    TYPE_PERSPECTIVE_BLUETOOTH,
    TYPE_PERSPECTIVE_FORM_SUBMISSION,
    TYPE_PERSPECTIVE_KEY_EVENT,
    TYPE_PERSPECTIVE_MESSAGE_HANDLER,
    TYPE_PERSPECTIVE_NFC_SCAN,
    TYPE_PERSPECTIVE_PAGE_CONFIG,
    TYPE_PERSPECTIVE_PAGE_STARTUP,
    TYPE_PERSPECTIVE_SESSION_PROPS,
    TYPE_PERSPECTIVE_SHUTDOWN,
    TYPE_PERSPECTIVE_STARTUP,
    TYPE_PERSPECTIVE_STYLE_CLASS,
    TYPE_PERSPECTIVE_STYLESHEET,
    TYPE_PERSPECTIVE_VIEW,
    TYPE_PROJECT_PROPERTIES,
    TYPE_REPORT,
    TYPE_SCRIPT_GATEWAY_EVENT,
    TYPE_SCRIPT_PYTHON,
    TYPE_SFC,
    TYPE_UNKNOWN,
)
from .models import ProjectExport, ProjectMeta, Resource, ResourceFile


def parse_project_export(
    zip_file: zipfile.ZipFile, project_root: str | None = None
) -> ProjectExport:
    """
    Parse an Ignition project archive.

    Args:
        zip_file: Open ZipFile instance.
        project_root: Optional project root prefix (e.g. "projects/MyProject/") for multi-project archives.

    Returns:
        ProjectExport: Parsed project model.

    Raises:
        ValueError: If project selection fails, project.json missing, or a resource manifest is invalid.
    """
    names = set(zip_file.namelist())

    selected_root = _select_project_root(names, project_root)
    project_meta = _read_project_json(zip_file, selected_root)

    resources = _discover_resources_by_manifest(zip_file, names, selected_root)

    # Stable ordering by section then path then resource_json_path.
    resources.sort(key=lambda r: (r.section, r.path, r.resource_json_path))

    return ProjectExport(project=project_meta, resources=resources, all_paths=names)


# -------------------------
# Project root selection
# -------------------------


def _select_project_root(names: set[str], project_root: str | None) -> str:
    """
    Determine the project root prefix within the ZIP.

    Rules:
    - If "project.json" exists at root, treat as Designer export => project_root = "".
    - Else find projects under projects/<name>/project.json (or Projects/<name>/project.json).
      - If exactly one project exists => select it.
      - If multiple => require `project_root`.

    Returns:
        str: Selected project root prefix ("" or "projects/<name>/").

    Raises:
        ValueError: If no project.json found, or multiple projects exist without selection.
    """
    if "project.json" in names:
        if project_root:
            # If caller provides a root but designer export exists, prefer explicit selection only if it exists.
            if project_root.rstrip("/") + "/project.json" in names:
                return project_root.rstrip("/") + "/"
        return ""

    # Gateway backup style
    candidates: list[str] = []
    for base in PROJECTS_DIR_CANDIDATES:
        for n in names:
            if not n.startswith(base) or not n.endswith("/project.json"):
                continue
            # n: projects/Template/project.json -> root projects/Template/
            root = n[: -len("project.json")]
            candidates.append(root)

    candidates = sorted(set(candidates))

    if project_root:
        pr = project_root.rstrip("/") + "/"
        if pr + "project.json" not in names:
            raise ValueError(f"project.json not found under selected project_root: {pr}")
        return pr

    if not candidates:
        raise ValueError(
            "project.json not found (expected root project.json or projects/<name>/project.json)"
        )

    if len(candidates) > 1:
        raise ValueError(f"multiple projects found; specify project_root. candidates={candidates}")

    return candidates[0]


def _read_project_json(zip_file: zipfile.ZipFile, root: str) -> ProjectMeta:
    """
    Read project.json at the selected root (strict).

    Args:
        zip_file: Open ZipFile.
        root: Project root prefix.

    Returns:
        ProjectMeta

    Raises:
        ValueError: If project.json is missing or invalid JSON.
    """
    pj = f"{root}project.json" if root else "project.json"
    raw_bytes = zip_file.read(pj)

    raw = _try_json(raw_bytes)
    if not isinstance(raw, dict):
        raise ValueError(f"project.json is not valid JSON object: {pj}")

    title = str(raw.get("title") or raw.get("name") or "Ignition Project")
    desc = raw.get("description")
    parent = raw.get("parent")

    return ProjectMeta(title=title, description=desc, parent=parent, raw=raw, project_root=root)


def _try_json(data: bytes) -> Any | None:
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


# -------------------------
# Manifest-driven discovery
# -------------------------


def _discover_resources_by_manifest(
    zip_file: zipfile.ZipFile, names: set[str], root: str
) -> list[Resource]:
    """
    Discover all resources by scanning for `resource.json` under `root`.

    For each resource.json:
    - parse it
    - read `files` list
    - validate declared files exist
    - classify type/section/path
    - build deterministic ResourceFile list:
        [resource.json] + manifest files + optional data.bin

    Args:
        zip_file: Open ZipFile.
        names: All zip internal paths.
        root: Selected project root prefix.

    Returns:
        list[Resource]
    """
    out: list[Resource] = []

    prefix = root  # can be "" for Designer export
    for rj in sorted(p for p in names if p.startswith(prefix) and p.endswith("/resource.json")):
        manifest = _read_resource_manifest(zip_file, rj)
        declared = manifest.get("files")

        if not isinstance(declared, list) or not all(isinstance(x, str) for x in declared):
            raise ValueError(f"Invalid resource.json (missing/invalid 'files') at: {rj}")

        folder = rj[: -len("resource.json")]  # includes trailing slash

        # Validate manifest files exist
        missing: list[str] = []
        for fname in declared:
            fpath = folder + fname
            if fpath not in names:
                missing.append(fpath)
        if missing:
            raise ValueError(
                f"Resource manifest declares missing files: {missing} (resource.json={rj})"
            )

        # Build file list: resource.json first, then manifest order, then optional data.bin
        files: list[ResourceFile] = [ResourceFile(zip_path=rj, kind="resource.json")]
        for fname in declared:
            fpath = folder + fname
            files.append(ResourceFile(zip_path=fpath, kind=_kind_for_file(fname)))

        # binary_only = (folder + "data.bin") in names
        # if binary_only:
        #     files.append(ResourceFile(zip_path=folder + "data.bin", kind="data.bin"))
        # binary_only: presence of data.bin in folder
        binary_path = folder + "data.bin"
        binary_only = binary_path in names

        # If data.bin exists but wasn't declared (defensive), append it once at end.
        declared_paths = {folder + f for f in declared}
        if binary_only and binary_path not in declared_paths:
            files.append(ResourceFile(zip_path=binary_path, kind="data.bin"))

        type_key, section, logical_path = _classify_resource(root, rj)

        out.append(
            Resource(
                type_key=type_key,
                path=logical_path,
                files=files,
                binary_only=binary_only,
                section=section,
                resource_json_path=rj,
                attributes=dict(manifest.get("attributes") or {}),
            )
        )

    return out


def _read_resource_manifest(zip_file: zipfile.ZipFile, resource_json_path: str) -> dict[str, Any]:
    """
    Read and parse a resource.json manifest.

    Args:
        zip_file: Open ZipFile.
        resource_json_path: ZIP internal path to resource.json.

    Returns:
        dict[str, Any]: Parsed JSON.

    Raises:
        ValueError: If JSON is invalid or not an object.
    """
    raw = _try_json(zip_file.read(resource_json_path))
    if not isinstance(raw, dict):
        raise ValueError(f"resource.json is not a JSON object: {resource_json_path}")
    return raw


def _kind_for_file(fname: str) -> str:
    """
    Map a manifest file name to a logical kind used downstream.

    Rules:
    - thumbnail.* => "thumbnail"
    - *.py => "script"
    - *.sql => "sql"
    - sfc.xml => "sfc.xml"
    - otherwise => exact filename ("view.json", "config.json", "style.json", "props.json", ...)
    """
    lower = fname.lower()

    if lower in (
        "thumbnail.png",
        "thumbnail.jpg",
        "thumbnail.jpeg",
        "thumb.png",
        "thumb.jpg",
        "thumb.jpeg",
    ):
        return "thumbnail"
    if lower.endswith(".py"):
        return "script"
    if lower.endswith(".sql"):
        return "sql"
    if lower == "sfc.xml":
        return "sfc.xml"
    return fname


# -------------------------
# Classification (v1: Perspective-focused)
# -------------------------


def _strip_prefix(s: str, prefix: str) -> str:
    return s[len(prefix) :] if s.startswith(prefix) else s


def _classify_resource(root: str, resource_json_path: str) -> tuple[str, str, str]:
    """
    Classify a resource based on its location relative to the project root.

    This classifier is intentionally location-based, but *manifest-driven* discovery
    ensures we're only classifying actual resources (folders with resource.json).

    Returns:
        (type_key, section, logical_path)
    """
    rel = _strip_prefix(resource_json_path, root)

    if not rel.endswith("/resource.json"):  # pragma: no cover
        return (TYPE_UNKNOWN, SECTION_PROPERTIES, rel)  # pragma: no cover

    rel_folder = rel[: -len("/resource.json")] + "/"

    # -------------------------
    # Perspective
    # -------------------------

    if rel_folder.startswith(PFX_PERSPECTIVE_VIEWS):
        view_path = rel_folder[len(PFX_PERSPECTIVE_VIEWS) :].rstrip("/")
        return (TYPE_PERSPECTIVE_VIEW, SECTION_PERSPECTIVE, view_path)

    if rel_folder == PFX_PERSPECTIVE_PAGE_CONFIG:
        return (
            TYPE_PERSPECTIVE_PAGE_CONFIG,
            SECTION_PERSPECTIVE,
            "page-config",
        )  # TODO remove hardcoded logical_path returns

    if rel_folder.startswith(PFX_PERSPECTIVE_STYLE_CLASSES):
        style_path = rel_folder[len(PFX_PERSPECTIVE_STYLE_CLASSES) :].rstrip("/")
        return (TYPE_PERSPECTIVE_STYLE_CLASS, SECTION_PERSPECTIVE, style_path)

    if rel_folder == PFX_PERSPECTIVE_STYLESHEET:
        return (TYPE_PERSPECTIVE_STYLESHEET, SECTION_PERSPECTIVE, "stylesheet")

    if rel_folder.startswith(PFX_PERSPECTIVE_MESSAGE):
        p = rel_folder[len(PFX_PERSPECTIVE_MESSAGE) :].rstrip("/")
        return (TYPE_PERSPECTIVE_MESSAGE_HANDLER, SECTION_PERSPECTIVE, f"message/{p}")

    if rel_folder.startswith(PFX_PERSPECTIVE_FORM_SUBMISSION):
        p = rel_folder[len(PFX_PERSPECTIVE_FORM_SUBMISSION) :].rstrip("/")
        return (
            TYPE_PERSPECTIVE_FORM_SUBMISSION,
            SECTION_PERSPECTIVE,
            f"form-submission-handler/{p}",
        )

    if rel_folder.startswith(PFX_PERSPECTIVE_KEY_EVENT):
        p = rel_folder[len(PFX_PERSPECTIVE_KEY_EVENT) :].rstrip("/")
        return (TYPE_PERSPECTIVE_KEY_EVENT, SECTION_PERSPECTIVE, f"key-event/{p}")

    if rel_folder.startswith(PFX_PERSPECTIVE_ACCELEROMETER):
        return (TYPE_PERSPECTIVE_ACCELEROMETER, SECTION_PERSPECTIVE, "accelerometer")

    if rel_folder.startswith(PFX_PERSPECTIVE_AUTH_CHALLENGE):
        return (TYPE_PERSPECTIVE_AUTH_CHALLENGE, SECTION_PERSPECTIVE, "auth-challenge")

    if rel_folder.startswith(PFX_PERSPECTIVE_BARCODE):
        return (TYPE_PERSPECTIVE_BARCODE, SECTION_PERSPECTIVE, "barcode")

    if rel_folder.startswith(PFX_PERSPECTIVE_BLUETOOTH):
        return (TYPE_PERSPECTIVE_BLUETOOTH, SECTION_PERSPECTIVE, "bluetooth")

    if rel_folder.startswith(PFX_PERSPECTIVE_NFC_SCAN):
        return (TYPE_PERSPECTIVE_NFC_SCAN, SECTION_PERSPECTIVE, "nfc-scan")

    if rel_folder.startswith(PFX_PERSPECTIVE_PAGE_STARTUP):
        return (TYPE_PERSPECTIVE_PAGE_STARTUP, SECTION_PERSPECTIVE, "page-startup")

    if rel_folder.startswith(PFX_PERSPECTIVE_SESSION_PROPS):
        return (TYPE_PERSPECTIVE_SESSION_PROPS, SECTION_PERSPECTIVE, "session-props")

    if rel_folder.startswith(PFX_PERSPECTIVE_STARTUP):
        return (TYPE_PERSPECTIVE_STARTUP, SECTION_PERSPECTIVE, "startup")

    if rel_folder.startswith(PFX_PERSPECTIVE_SHUTDOWN):
        return (TYPE_PERSPECTIVE_SHUTDOWN, SECTION_PERSPECTIVE, "shutdown")

    # -------------------------
    # Alarm pipelines / Event streams / Reports / SFC
    # -------------------------

    if rel_folder.startswith(PFX_ALARM_PIPELINES):
        p = rel_folder[len(PFX_ALARM_PIPELINES) :].rstrip("/")
        return (TYPE_ALARM_PIPELINE, SECTION_ALARM_PIPELINES, p)

    if rel_folder.startswith(PFX_EVENT_STREAMS):
        p = rel_folder[len(PFX_EVENT_STREAMS) :].rstrip("/")
        return (TYPE_EVENT_STREAM, SECTION_EVENT_STREAMS, p)

    if rel_folder.startswith(PFX_REPORTS):
        p = rel_folder[len(PFX_REPORTS) :].rstrip("/")
        return (TYPE_REPORT, SECTION_REPORTS, p)

    if rel_folder.startswith(PFX_SFC):
        p = rel_folder[len(PFX_SFC) :].rstrip("/")
        return (TYPE_SFC, SECTION_SFC, p)

    # -------------------------
    # Ignition folder (scripts, named queries, project properties)
    # -------------------------

    if rel_folder.startswith(PFX_IGNITION_SCRIPT_PYTHON):
        p = rel_folder[len(PFX_IGNITION_SCRIPT_PYTHON) :].rstrip("/")
        return (TYPE_SCRIPT_PYTHON, SECTION_SCRIPTS, p)

    if rel_folder.startswith(PFX_IGNITION_NAMED_QUERY):
        p = rel_folder[len(PFX_IGNITION_NAMED_QUERY) :].rstrip("/")
        return (TYPE_NAMED_QUERY, SECTION_NAMED_QUERIES, p)

    if rel_folder.startswith(PFX_IGNITION_GLOBAL_PROPS):
        return (TYPE_PROJECT_PROPERTIES, SECTION_PROPERTIES, "global-props")

    # Ignition gateway event scripts: ignition/startup/<name>, ignition/shutdown, etc.
    for pfx in (
        PFX_IGNITION_MESSAGE,
        PFX_IGNITION_SCHEDULED,
        PFX_IGNITION_SHUTDOWN,
        PFX_IGNITION_STARTUP,
        PFX_IGNITION_TAG_CHANGE,
        PFX_IGNITION_TIMER,
        PFX_IGNITION_UPDATE,
    ):
        if rel_folder.startswith(pfx):
            p = rel_folder[len(pfx) :].rstrip("/")
            kind = pfx.rstrip("/").split("/")[-1]
            logical = f"{kind}/{p}" if p else kind
            return (TYPE_SCRIPT_GATEWAY_EVENT, SECTION_SCRIPTS, logical)

    # Default fallback
    if rel_folder.startswith("com.inductiveautomation.perspective/"):  # pragma: no cover
        return (
            TYPE_UNKNOWN,
            SECTION_PERSPECTIVE,
            rel_folder.rstrip("/"),
        )  # pragma: no cover

    return (TYPE_UNKNOWN, SECTION_PROPERTIES, rel_folder.rstrip("/"))
