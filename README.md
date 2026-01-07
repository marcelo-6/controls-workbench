# Controls Workbench (v0.1)

A local-first desktop companion app (web UI + API) for exploring automation projects.

## What’s included

- **Frontend**: React + MUI + ReactFlow
- **Backend**: FastAPI + Huey (SQLite-backed queue)
- **Persistence**: a single `/data` directory (uploads, runs, logs, queue db)

## Quickstart (Docker)

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build
```

3. Open the UI:

- http://localhost:5173

## App password

Set `APP_PASSWORD` in `.env` (or use the default `change-me`).

## Data layout

All persistent files live under the `./data/` folder on the host:

- `data/uploads/<upload_id>/...`
- `data/runs/<job_id>/...`
- `data/logs/api.log` and `data/logs/worker.log`
- `data/queue/queue.db`

## Tool: Ignition Project Explorer Graph

Upload an Ignition project export zip (and optional tags export JSON), then run the graph job.

Artifacts per run:

- `graph/graph.json`
- `report/report.json`
- `report/summary.md`

## Dev (no Docker)

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Worker:

```bash
cd backend
. .venv/bin/activate
huey_consumer.py app.queue.huey
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
```
