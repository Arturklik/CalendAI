"""Схемы дифференциальной синхронизации (POST /api/v1/sync)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .event import EventResponse, EventSyncItem


class SyncRequest(BaseModel):
    """Запрос синхронизации от Flutter-клиента.

    `last_sync_timestamp` — значение `sync_timestamp` из предыдущего
    успешного ответа сервера; `None` при первичной синхронизации.
    """

    last_sync_timestamp: datetime | None = None
    client_changes: list[EventSyncItem] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """Ответ сервера: новая метка синхронизации + серверные изменения."""

    sync_timestamp: datetime
    server_changes: list[EventResponse] = Field(default_factory=list)
