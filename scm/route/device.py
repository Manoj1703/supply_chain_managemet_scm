from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import ServerSelectionTimeoutError

from database.db import list_devices
from model.device import DeviceEvent, DevicePublic
from services.auth_service import get_current_user
from services.kafka_service import publish_device_event


router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/", response_model=list[DevicePublic], summary="List devices")
def get_devices(_current_user: dict[str, object] = Depends(get_current_user)) -> list[dict[str, object]]:
    return list_devices()


@router.post("/events", summary="Ingest device event")
def ingest_device_event(
    payload: DeviceEvent,
    _current_user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return publish_device_event(payload.model_dump())
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected",
        ) from exc
