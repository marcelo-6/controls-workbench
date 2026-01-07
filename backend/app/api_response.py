from __future__ import annotations

from typing import TypeVar

from .api_models import APIError, APIMeta, APIResponse, ErrorField, Status

T = TypeVar("T")


def ok(data: T, message: str | None = None, request_id: str | None = None) -> APIResponse[T]:
    meta = APIMeta(request_id=request_id)
    return APIResponse[T](status=Status.success, message=message, data=data, meta=meta, error=None)


def fail(
    code: str,
    detail: str,
    message: str | None = None,
    request_id: str | None = None,
    fields: list[ErrorField] | None = None,
) -> APIResponse[None]:
    meta = APIMeta(request_id=request_id)
    err = APIError(code=code, detail=detail, fields=fields or [])
    return APIResponse[None](
        status=Status.error, message=message or detail, data=None, meta=meta, error=err
    )
