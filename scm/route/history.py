from __future__ import annotations

from fastapi import APIRouter, Depends

from database.db import list_history
from model.history import HistoryEntry
from services.auth_service import get_current_user


router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/", response_model=list[HistoryEntry], summary="List history")
def get_history(_current_user: dict[str, object] = Depends(get_current_user)) -> list[dict[str, object]]:
    return list_history()
