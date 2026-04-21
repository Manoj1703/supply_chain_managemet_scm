from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DeviceEvent(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=100)
    status: str = Field(default="online", max_length=50)
    location: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DevicePublic(BaseModel):
    id: str
    device_id: str
    name: str
    status: str
    location: str | None = None
    source: str | None = None

