from __future__ import annotations

from pydantic import BaseModel


class HistoryEntry(BaseModel):
    id: str
    kind: str
    message: str
    entity_id: str | None = None
