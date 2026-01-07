from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .api_models import JobStatus, ToolCategory
from .config import settings
from .ignition.engine import build_graph
from .ignition.parser import safe_extract_zip
from .logging_conf import setup_logger
from .queue import huey
from .run_models import InputFile, RunMeta, RunState, Stats, Versions, utcnow
from .run_storage import append_event, run_dir, write_meta, write_state
from .tools_registry import Tool, register
from .uploads_storage import file_sha256, find_project_zip, find_tags_json

worker_logger = setup_logger("worker", str(Path(settings.data_dir) / "logs" / "worker.log"))


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def run_ignition_graph(job_id: str, upload_id: str, params: dict) -> None:
    rd = run_dir(job_id)
    rd.mkdir(parents=True, exist_ok=True)

    project_zip = find_project_zip(upload_id)
    if not project_zip:
        raise FileNotFoundError("project zip not found for upload_id")

    tags_json = find_tags_json(upload_id)

    # Copy inputs for traceability
    inputs_dir = rd / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    proj_copy = inputs_dir / project_zip.name
    shutil.copy2(project_zip, proj_copy)

    tag_copy = None
    if tags_json:
        tag_copy = inputs_dir / tags_json.name
        shutil.copy2(tags_json, tag_copy)

    meta = RunMeta(
        job_id=job_id,
        tool_id="ignition.graph",
        created_at=utcnow(),
        last_accessed_at=utcnow(),
        input_files=[
            InputFile(
                name=proj_copy.name,
                size_bytes=proj_copy.stat().st_size,
                sha256=file_sha256(proj_copy),
            ),
        ],
        versions=Versions(app_version="0.1.0", parser_version="0.1.0"),
        stats=Stats(),
    )
    if tag_copy:
        meta.input_files.append(
            InputFile(
                name=tag_copy.name, size_bytes=tag_copy.stat().st_size, sha256=file_sha256(tag_copy)
            )
        )

    write_meta(meta)

    # Extract zip
    append_event(job_id, "Starting: extracting zip")
    worker_logger.info("job=%s extracting zip", job_id)

    extract_dir = rd / "work" / "project"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    safe_extract_zip(proj_copy, extract_dir)

    append_event(job_id, "Starting: scanning + building graph")
    worker_logger.info("job=%s building graph", job_id)

    graph, report, summary_md = build_graph(extract_dir, job_id)

    # Write artifacts
    (rd / "graph").mkdir(parents=True, exist_ok=True)
    (rd / "report").mkdir(parents=True, exist_ok=True)

    (rd / "graph" / "graph.json").write_text(
        graph.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
    )
    _write_json(rd / "report" / "report.json", report)
    (rd / "report" / "summary.md").write_text(summary_md, encoding="utf-8")

    # Update meta stats
    meta.stats.parse_seconds = graph.meta.stats.get("parse_seconds")
    meta.stats.nodes = graph.meta.stats.get("nodes")
    meta.stats.edges = graph.meta.stats.get("edges")
    meta.stats.counts_by_type = graph.meta.stats.get("counts_by_type", {})
    write_meta(meta)

    append_event(job_id, "Done: artifacts written")
    worker_logger.info("job=%s done", job_id)


@huey.task()
def run_tool_job(job_id: str, tool_id: str, upload_id: str, params: dict) -> None:
    t0 = time.time()
    state = RunState(job_id=job_id, tool_id=tool_id, status=JobStatus.running, started_at=utcnow())
    write_state(state)

    try:
        append_event(job_id, f"Job running: {tool_id}")
        if tool_id == "ignition.graph":
            run_ignition_graph(job_id, upload_id, params)
        else:
            raise ValueError(f"Unknown tool_id: {tool_id}")

        state.status = JobStatus.success
        state.finished_at = utcnow()
        state.progress_hint = f"Completed in {round(time.time() - t0, 2)}s"
        write_state(state)
        append_event(job_id, "Job success")

    except Exception as e:
        worker_logger.exception("job=%s failed: %s", job_id, e)
        state.status = JobStatus.failed
        state.finished_at = utcnow()
        state.progress_hint = str(e)
        write_state(state)
        append_event(job_id, f"Job failed: {e}")
        raise


# Register tools (import side-effect is fine for v0.1)
register(
    Tool(
        tool_id="ignition.graph",
        name="Ignition Project Explorer Graph",
        category=ToolCategory.ignition,
        version="0.1.0",
        runner=lambda job_id, upload_id, params: run_tool_job(
            job_id, "ignition.graph", upload_id, params
        ),
    )
)
