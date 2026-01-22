# backend/app/tools/ignition/project_explorer/parser.py
"""
Ignition Designer project export ZIP parser.

This module parses a *single* Ignition Designer project export ZIP (v1) and
produces an in-memory representation of project resources sufficient to build:

- a Designer-ordered tree (sections + folders + leaf nodes)
- a dependency graph (nodes + edges)
- per-node "source" artifacts for fast frontend rendering:
  - view.json bodies
  - scripts (.py)
  - named query SQL
  - resource.json / config.json (when present)
  - thumbnails for Perspective views

Scope notes (v1):
- Input: Designer project export ZIP only.
- Tags: Not parsed from Gateway backups; tag export JSON may be added later.
- Binary-only resources (resource.json + data.bin): represented as nodes only.

The parser intentionally avoids any DB or filesystem writes. It reads ZIP entries
and returns structured metadata + access to raw ZIP contents via helper methods.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectMeta:
    """
    Minimal project metadata.

    Attributes:
        title: Project title/name (best-effort from project.json).
        description: Project description (best-effort).
        parent: Parent project raw string (if project inheritance is configured).
        raw: Raw parsed project.json dict (best-effort).
    """

    title: str
    description: str | None
    parent: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ResourceFile:
    """
    A discovered resource file inside the export.

    Attributes:
        zip_path: ZIP internal path.
        kind: Logical kind (e.g. "view.json", "thumbnail", "script", "sql", "resource.json", "config.json", "data.bin").
    """

    zip_path: str
    kind: str


@dataclass(frozen=True)
class Resource:
    """
    A discovered Ignition resource folder (logical resource).

    Attributes:
        type_key: High-level resource type key (e.g. "perspective.view", "script.python", "named_query").
        path: Designer-like logical path (e.g. "Exchange/Dash/Dash" for views).
        files: Files relevant for this resource.
        binary_only: True if the resource contains data.bin (binary-only config).
        section: Designer tree section label (used for ordering).
    """

    type_key: str
    path: str
    files: list[ResourceFile]
    binary_only: bool
    section: str


class ProjectExport:
    """
    Parsed project export representation backed by a ZIP file.

    The object stores a ZIP path index and provides methods for reading file bytes.
    """

    def __init__(
        self, *, project: ProjectMeta, resources: list[Resource], all_paths: set[str]
    ) -> None:
        self.project = project
        self.resources = resources
        self._all_paths = all_paths

    def has_path(self, zip_path: str) -> bool:
        """Return True if the ZIP contains the given internal path."""
        return zip_path in self._all_paths

    def iter_resources(self) -> Iterable[Resource]:
        """Iterate discovered resources."""
        return iter(self.resources)


# -------------------------
# Parser entrypoint
# -------------------------


def parse_project_export(zip_file: zipfile.ZipFile) -> ProjectExport:
    """
    Parse an Ignition Designer project export ZIP.

    Args:
        zip_file: Open ZipFile instance.

    Returns:
        ProjectExport: Parsed project model (resources + minimal metadata).
    """
    names = set(zip_file.namelist())

    project_meta = _read_project_json(zip_file)

    resources: list[Resource] = []
    resources.extend(_discover_perspective(zip_file, names))
    resources.extend(_discover_scripts(zip_file, names))
    resources.extend(_discover_named_queries(zip_file, names))
    resources.extend(_discover_sfc(zip_file, names))
    resources.extend(_discover_event_streams(zip_file, names))
    resources.extend(_discover_reports(zip_file, names))
    resources.extend(_discover_alarm_pipelines(zip_file, names))
    resources.extend(_discover_project_properties(zip_file, names))

    # Stable ordering within sections by path.
    resources.sort(key=lambda r: (r.section, r.path))

    return ProjectExport(project=project_meta, resources=resources, all_paths=names)


def _read_project_json(zip_file: zipfile.ZipFile) -> ProjectMeta:
    """
    Read project.json at ZIP root (best-effort).

    Returns:
        ProjectMeta
    """
    raw: dict[str, Any] = {}
    title = "Ignition Project"
    desc = None
    parent = None

    if "project.json" in zip_file.namelist():
        try:
            data = zip_file.read("project.json")
            raw = _try_json(data) or {}
            title = str(raw.get("title") or raw.get("name") or title)
            desc = raw.get("description")
            parent = raw.get("parent")
        except Exception:
            pass

    return ProjectMeta(title=title, description=desc, parent=parent, raw=raw)


def _try_json(data: bytes) -> Any | None:
    try:
        import json

        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


# -------------------------
# Discovery helpers
# -------------------------


def _folder_of(path: str) -> str:
    p = path.rstrip("/")
    if "/" not in p:
        return ""
    return p.rsplit("/", 1)[0] + "/"


def _find_files_under(names: set[str], prefix: str) -> list[str]:
    return [n for n in names if n.startswith(prefix) and not n.endswith("/")]


def _contains(names: set[str], path: str) -> bool:
    return path in names


# Designer-like section labels (only included if present)
_SECTION_PERSPECTIVE = "Perspective"
_SECTION_SCRIPTS = "Scripting"
_SECTION_NAMED_QUERIES = "Named Queries"
_SECTION_SFC = "Sequential Function Charts (SFC)"
_SECTION_EVENT_STREAMS = "Event Streams"
_SECTION_REPORTS = "Reports"
_SECTION_ALARM_PIPELINES = "Alarm Notification Pipelines"
_SECTION_PROPERTIES = "Properties"


def _discover_perspective(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    """
    Discover Perspective resources:
    - Views: com.inductiveautomation.perspective/views/<viewPath>/view.json (+ thumbnail.png)
    - Styles: com.inductiveautomation.perspective/styles/...
    - Session events: com.inductiveautomation.perspective/session-events/...
    - Page config: com.inductiveautomation.perspective/page-config/config.json
    """
    out: list[Resource] = []

    # Views
    views_prefix = "com.inductiveautomation.perspective/views/"
    for n in list(names):
        if not n.startswith(views_prefix) or not n.endswith("/view.json"):
            continue
        rel = n[len(views_prefix) :]
        view_path = rel[: -len("/view.json")]

        folder = _folder_of(n)
        files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="view.json")]

        # thumbnail (best-effort)
        for thumb in (
            "thumbnail.png",
            "thumbnail.jpg",
            "thumbnail.jpeg",
            "thumb.png",
            "thumb.jpg",
        ):
            tpath = folder + thumb
            if _contains(names, tpath):
                files.append(ResourceFile(zip_path=tpath, kind="thumbnail"))
                break

        # resource/config for debugging if present
        for extra in ("resource.json", "config.json"):
            ep = folder + extra
            if _contains(names, ep):
                files.append(ResourceFile(zip_path=ep, kind=extra))

        binary_only = _contains(names, folder + "data.bin")

        out.append(
            Resource(
                type_key="perspective.view",
                path=view_path,
                files=files,
                binary_only=binary_only,
                section=_SECTION_PERSPECTIVE,
            )
        )

    # Styles (resource.json)
    styles_prefix = "com.inductiveautomation.perspective/stylesheet/"
    for n in list(names):
        if not n.startswith(styles_prefix) or not n.endswith("/resource.json"):
            continue
        rel = n[len(styles_prefix) :]
        style_path = rel[: -len("/resource.json")]
        folder = _folder_of(n)
        files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]
        if _contains(names, folder + "stylesheet.css"):
            files.append(ResourceFile(zip_path=folder + "stylesheet.css", kind="stylesheet.css"))
        binary_only = _contains(names, folder + "data.bin")
        out.append(
            Resource(
                type_key="perspective.style_class",
                path=style_path,
                files=files,
                binary_only=binary_only,
                section=_SECTION_PERSPECTIVE,
            )
        )
    styles_prefix = "com.inductiveautomation.perspective/style-classes/"
    for n in list(names):
        if not n.startswith(styles_prefix) or not n.endswith("/resource.json"):
            continue
        rel = n[len(styles_prefix) :]
        style_path = rel[: -len("/resource.json")]
        folder = _folder_of(n)
        files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]
        if _contains(names, folder + "style.json"):
            files.append(ResourceFile(zip_path=folder + "style.json", kind="style.json"))
        binary_only = _contains(names, folder + "data.bin")
        out.append(
            Resource(
                type_key="perspective.style_class",
                path=style_path,
                files=files,
                binary_only=binary_only,
                section=_SECTION_PERSPECTIVE,
            )
        )

    # Page config
    page_cfg = "com.inductiveautomation.perspective/page-config/config.json"
    if _contains(names, page_cfg):
        out.append(
            Resource(
                type_key="perspective.page_config",
                path="page-config",
                files=[ResourceFile(zip_path=page_cfg, kind="config.json")],
                binary_only=False,
                section=_SECTION_PERSPECTIVE,
            )
        )

    # Session events (names-only + raw file bodies where available)
    SESSION_PREFIX = "com.inductiveautomation.perspective/"
    sess_prefix = [
        f"{SESSION_PREFIX}accelerometer",
        f"{SESSION_PREFIX}auth-challenge",
        f"{SESSION_PREFIX}barcode",
        f"{SESSION_PREFIX}bluetooth",
        f"{SESSION_PREFIX}form-submission-handler",
        f"{SESSION_PREFIX}key-event",
        f"{SESSION_PREFIX}message",
        f"{SESSION_PREFIX}nfc-scan",
        f"{SESSION_PREFIX}page-config",
        f"{SESSION_PREFIX}page-startup",
        f"{SESSION_PREFIX}session-props",
        f"{SESSION_PREFIX}shutdown",
        f"{SESSION_PREFIX}startup",
    ]

    for pref in sess_prefix:
        for n in list(names):
            # Only match folders that contain a session-event resource.json
            if not n.startswith(pref) or not n.endswith("/resource.json"):
                continue

            rel = n[len(pref) :]
            p = rel[: -len("/resource.json")]
            folder = _folder_of(n)

            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]

            # Optional config.json
            if _contains(names, folder + "config.json"):
                files.append(ResourceFile(zip_path=folder + "config.json", kind="config.json"))

            # Optional data.bin
            binary_only = _contains(names, folder + "data.bin")

            # collect all Python files under this folder
            for fname in names:
                if fname.startswith(folder) and fname.endswith(".py"):
                    files.append(ResourceFile(zip_path=fname, kind="script"))

            out.append(
                Resource(
                    type_key="perspective.session_event",
                    path=p,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_PERSPECTIVE,
                )
            )

    return out


def _discover_scripts(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    """
    Discover scripting resources (best-effort) by locating .py files under
    known Ignition export folders.
    """
    out: list[Resource] = []

    # Common project library scripts
    script_prefixes = [
        "ignition/script-python/",
        "com.inductiveautomation.ignition/scripting/",
    ]

    for pref in script_prefixes:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith(".py"):
                continue
            rel = n[len(pref) :]
            path = rel.replace(".py", "")
            files = [ResourceFile(zip_path=n, kind="script")]
            out.append(
                Resource(
                    type_key="script.python",
                    path=path,
                    files=files,
                    binary_only=False,
                    section=_SECTION_SCRIPTS,
                )
            )

    # Gateway event scripts sometimes exist as .py in exports (best-effort)
    evt_prefix = [
        "ignition/message/",
        "ignition/scheduled/",
        "ignition/shutdown/",
        "ignition/startup",
        "ignition/tag-change",
        "ignition/timer",
        "ignition/update",
    ]
    for pref in evt_prefix:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith(".py"):
                continue
            rel = n[len(pref) :]
            path = rel.replace(".py", "")
            out.append(
                Resource(
                    type_key="script.gateway_event",
                    path=path,
                    files=[ResourceFile(zip_path=n, kind="script")],
                    binary_only=False,
                    section=_SECTION_SCRIPTS,
                )
            )

    return out


def _discover_named_queries(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    """
    Discover Named Queries by locating .sql files under known export locations.
    """
    out: list[Resource] = []
    prefixes = [
        "com.inductiveautomation.ignition/named-query/",
        "ignition/named-queries/",
        "ignition/named-query/",
    ]
    for pref in prefixes:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith(".sql"):
                continue
            rel = n[len(pref) :]
            path = rel.replace(".sql", "")
            folder = _folder_of(n)
            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="sql")]
            if _contains(names, folder + "resource.json"):
                files.append(ResourceFile(zip_path=folder + "resource.json", kind="resource.json"))
            if _contains(names, folder + "config.json"):
                files.append(ResourceFile(zip_path=folder + "config.json", kind="config.json"))
            binary_only = _contains(names, folder + "data.bin")
            out.append(
                Resource(
                    type_key="named_query",
                    path=path,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_NAMED_QUERIES,
                )
            )
    return out


def _discover_sfc(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    out: list[Resource] = []
    prefixes = [
        "com.inductiveautomation.ignition/sfc/",
        "ignition/sfc/",
        "com.inductiveautomation.sfc/charts",
    ]
    for pref in prefixes:
        for n in list(names):
            if not n.startswith(pref) or not (n.endswith(".xml") or n.endswith("sfc.xml")):
                continue
            rel = n[len(pref) :]
            path = rel.replace("sfc.xml", "").replace(".xml", "").strip("/")
            folder = _folder_of(n)
            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="sfc.xml")]
            if _contains(names, folder + "resource.json"):
                files.append(ResourceFile(zip_path=folder + "resource.json", kind="resource.json"))
            binary_only = _contains(names, folder + "data.bin")
            out.append(
                Resource(
                    type_key="sfc",
                    path=path,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_SFC,
                )
            )
    return out


def _discover_event_streams(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    out: list[Resource] = []
    prefixes = [
        "com.inductiveautomation.ignition/event-streams/",
        "ignition/event-streams/",
        "com.inductiveautomation.eventstream/event-streams",
    ]
    for pref in prefixes:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith("/resource.json"):
                continue
            rel = n[len(pref) :]
            path = rel[: -len("/resource.json")]
            folder = _folder_of(n)
            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]
            if _contains(names, folder + "config.json"):
                files.append(ResourceFile(zip_path=folder + "config.json", kind="config.json"))
            binary_only = _contains(names, folder + "data.bin")
            out.append(
                Resource(
                    type_key="event_stream",
                    path=path,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_EVENT_STREAMS,
                )
            )
    return out


def _discover_reports(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    out: list[Resource] = []
    prefixes = [
        "com.inductiveautomation.reporting/reports/",
        "ignition/reports/",
        "com.inductiveautomation.reporting/reports",
    ]
    for pref in prefixes:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith("/resource.json"):
                continue
            rel = n[len(pref) :]
            path = rel[: -len("/resource.json")]
            folder = _folder_of(n)
            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]
            binary_only = _contains(names, folder + "data.bin")
            out.append(
                Resource(
                    type_key="report",
                    path=path,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_REPORTS,
                )
            )
    return out


def _discover_alarm_pipelines(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    out: list[Resource] = []
    prefixes = [
        "com.inductiveautomation.ignition/alarm-notification/",
        "ignition/alarm-notification/",
        "com.inductiveautomation.alarm-notification/alarm-pipelines/",
    ]
    for pref in prefixes:
        for n in list(names):
            if not n.startswith(pref) or not n.endswith("/resource.json"):
                continue
            rel = n[len(pref) :]
            path = rel[: -len("/resource.json")]
            folder = _folder_of(n)
            files: list[ResourceFile] = [ResourceFile(zip_path=n, kind="resource.json")]
            binary_only = _contains(names, folder + "data.bin")
            out.append(
                Resource(
                    type_key="alarm_pipeline",
                    path=path,
                    files=files,
                    binary_only=binary_only,
                    section=_SECTION_ALARM_PIPELINES,
                )
            )
    return out


def _discover_project_properties(zip_file: zipfile.ZipFile, names: set[str]) -> list[Resource]:
    out: list[Resource] = []
    # Typically: ignition/project-properties/resource.json or similar
    candidates = [
        "ignition/project-properties/resource.json",
        "ignition/project.json",
        "com.inductiveautomation.ignition/project-properties/resource.json",
    ]
    for c in candidates:
        if _contains(names, c):
            out.append(
                Resource(
                    type_key="project_properties",
                    path="project-properties",
                    files=[ResourceFile(zip_path=c, kind="resource.json")],
                    binary_only=False,
                    section=_SECTION_PROPERTIES,
                )
            )
    return out
