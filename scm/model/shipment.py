from __future__ import annotations

from pydantic import BaseModel, Field


class ShipmentCreate(BaseModel):
    shipment_id: str | None = Field(default=None, max_length=50)
    sender: str = Field(min_length=1, max_length=120)
    receiver: str = Field(min_length=1, max_length=120)
    status: str = Field(default="pending", max_length=50)
    eta: str | None = Field(default=None, max_length=120)
    details: str | None = Field(default=None, max_length=500)


class ShipmentPublic(BaseModel):
    id: str
    shipment_id: str
    sender: str
    receiver: str
    status: str
    eta: str | None = None
    details: str | None = None
