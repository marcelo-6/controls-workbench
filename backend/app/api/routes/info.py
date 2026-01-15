from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas.info import InfoResponse
from app.core.responses import APIResponse, ok
from app.core.settings import Settings, get_settings

router = APIRouter(tags=["info"])


@router.get("/info", response_model=APIResponse[InfoResponse])
async def info(
    settings: Annotated[Settings, Depends(get_settings)],
) -> APIResponse[InfoResponse]:
    """
    Return basic backend metadata and runtime configuration hints.

    This endpoint is intentionally lightweight and stable. It exists to support:
    - UI display of backend version/name
    - basic diagnostics (e.g., verifying the server is pointing at the expected data_dir)
    - smoke testing during development and deployment

    Returns:
        APIResponse[InfoResponse]: Standard response envelope containing backend info.
    """
    return ok(
        InfoResponse(
            backend_name=settings.project_name,
            backend_version=settings.backend_version,
            backend_description=settings.project_description,
            data_dir=str(settings.data_dir),
        )
    )
