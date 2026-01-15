from __future__ import annotations

from pydantic import BaseModel


class InfoResponse(BaseModel):
    backend_name: str
    backend_version: str
    backend_description: str
    data_dir: str
