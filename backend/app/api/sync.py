"""Эндпоинт дифференциальной синхронизации: POST /api/v1/sync.

Главная точка интеграции Flutter-клиента (SyncRepository).
Логика — в app/services/sync_service.py (Last-Write-Wins).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..schemas.sync import SyncRequest, SyncResponse
from ..services import sync_service
from .deps import get_current_user

router = APIRouter(tags=["sync"])


@router.post("/sync", response_model=SyncResponse)
async def sync(
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncResponse:
    """Двусторонняя синхронизация событий пользователя."""
    return await sync_service.synchronize(db, current_user.id, request)
