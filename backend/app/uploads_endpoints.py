from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from .api_models import APIResponse, UploadCreated, UploadFileInfo
from .api_response import ok
from .auth import require_auth
from .storage import data_path
from .uploads_storage import upload_dir

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _save_upload(dst: Path, up: UploadFile) -> int:
    size = 0
    with dst.open("wb") as f:
        while True:
            chunk = up.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Upload too large")
            f.write(chunk)
    return size


@router.post("", response_model=APIResponse[UploadCreated])
def create_upload(
    request: Request,
    project_zip: UploadFile = File(...),
    tags_json: UploadFile | None = File(default=None),
    user: str = Depends(require_auth),
):
    if not project_zip.filename or not project_zip.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="project_zip must be a .zip file")
    if tags_json and (not tags_json.filename or not tags_json.filename.lower().endswith(".json")):
        raise HTTPException(status_code=400, detail="tags_json must be a .json file")

    upload_id = str(uuid.uuid4())
    d = upload_dir(upload_id)
    d.mkdir(parents=True, exist_ok=True)

    received = []

    zip_path = d / Path(project_zip.filename).name
    zip_size = _save_upload(zip_path, project_zip)
    received.append(UploadFileInfo(name=zip_path.name, size_bytes=zip_size))

    if tags_json:
        json_path = d / Path(tags_json.filename).name
        json_size = _save_upload(json_path, tags_json)
        received.append(UploadFileInfo(name=json_path.name, size_bytes=json_size))

    return ok(UploadCreated(upload_id=upload_id, received_files=received), message="Upload received", request_id=getattr(request.state, "request_id", None))


@router.get("/{upload_id}", response_model=APIResponse[UploadCreated])
def get_upload(request: Request, upload_id: str, user: str = Depends(require_auth)):
    d = upload_dir(upload_id)
    if not d.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    received = []
    for fp in d.iterdir():
        if fp.is_file():
            received.append(UploadFileInfo(name=fp.name, size_bytes=fp.stat().st_size))
    return ok(UploadCreated(upload_id=upload_id, received_files=received), request_id=getattr(request.state, "request_id", None))
