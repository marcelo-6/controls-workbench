from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.schemas.info import InfoResponse

# from app.core.responses import APIResponse, ok
from app.core.settings import Settings, get_settings

router = APIRouter(tags=["info"])


# @router.get("/info", response_model=APIResponse[InfoResponse])
# @router.get("/info")
# async def info(settings: Settings = Depends(get_settings)) -> APIResponse[InfoResponse]:
#     return ok(
#         InfoResponse(
#             backend_name=settings.project_name,
#             backend_version=settings.backend_version,
#             backend_description=settings.project_description,
#             data_dir=str(settings.data_dir),
#         )
#     )


@router.get("/info")
async def info(settings: Settings = Depends(get_settings)):
    return InfoResponse(
        backend_name=settings.project_name,
        backend_version=settings.backend_version,
        backend_description=settings.project_description,
        data_dir=str(settings.data_dir),
    )
