from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError
from pymongo.errors import ServerSelectionTimeoutError

from database.db import create_shipment, list_shipments
from model.shipment import ShipmentCreate, ShipmentPublic
from services.auth_service import get_current_user


router = APIRouter(prefix="/api/shipments", tags=["shipments"])


@router.get("/", response_model=list[ShipmentPublic], summary="List shipments")
def get_shipments(_current_user: dict[str, object] = Depends(get_current_user)) -> list[dict[str, object]]:
    return list_shipments()


@router.post("/", response_model=ShipmentPublic, status_code=status.HTTP_201_CREATED, summary="Create shipment")
def add_shipment(
    payload: ShipmentCreate,
    _current_user: dict[str, object] = Depends(get_current_user),
) -> ShipmentPublic:
    try:
        shipment = create_shipment(
            shipment_id=payload.shipment_id,
            sender=payload.sender,
            receiver=payload.receiver,
            status=payload.status,
            eta=payload.eta,
            details=payload.details,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment already exists",
        ) from exc
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected",
        ) from exc

    return ShipmentPublic(
        id=shipment["id"],
        shipment_id=shipment["shipment_id"],
        sender=shipment["sender"],
        receiver=shipment["receiver"],
        status=shipment["status"],
        eta=shipment.get("eta"),
        details=shipment.get("details"),
    )
