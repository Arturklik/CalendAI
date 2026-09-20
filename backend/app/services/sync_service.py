"""Дифференциальная синхронизация по алгоритму Last-Write-Wins (LWW).

Контракт (см. AGENTS.md и lib/repositories/sync_repository.dart):
клиент шлёт `last_sync_timestamp` + список локальных изменений, сервер
применяет новые изменения и возвращает `sync_timestamp` + события,
изменившиеся на сервере с момента последнего синка (включая tombstone
записи с is_deleted=True).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.event import Event
from ..schemas.event import EventResponse, EventSyncItem
from ..schemas.sync import SyncRequest, SyncResponse


def _as_utc(value: datetime) -> datetime:
    """Приводит datetime к aware-UTC (SQLite возвращает naive-метки)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _apply_changes(db_event: Event, change: EventSyncItem) -> None:
    """Переносит все поля клиентской версии в ORM-объект (LWW-update)."""
    db_event.title = change.title
    db_event.event_type = change.event_type.value
    db_event.start_time = change.start_time
    db_event.end_time = change.end_time
    db_event.location = change.location
    db_event.teacher = change.teacher
    db_event.description = change.description
    db_event.recurrence_rule = change.recurrence_rule
    db_event.updated_at = change.updated_at
    db_event.is_deleted = change.is_deleted


async def synchronize(
    db: AsyncSession, user_id: uuid.UUID, request: SyncRequest
) -> SyncResponse:
    """Выполняет двустороннюю дифференциальную синхронизацию.

    Вся операция — одна транзакция: либо применяются все клиентские
    изменения, либо ни одного.
    """
    # 1. Серверное время фиксируется в начале операции.
    server_sync_time = datetime.now(timezone.utc)

    last_sync = (
        _as_utc(request.last_sync_timestamp)
        if request.last_sync_timestamp is not None
        else None
    )

    accepted_ids: set[uuid.UUID] = set()

    # Дедупликация внутри батча: если клиент прислал одно событие
    # несколько раз, применяем самую новую версию (LWW внутри батча).
    changes_by_id: dict[uuid.UUID, EventSyncItem] = {}
    for change in request.client_changes:
        existing = changes_by_id.get(change.id)
        if existing is None or change.updated_at >= existing.updated_at:
            changes_by_id[change.id] = change

    # 2. Применяем клиентские изменения (Last-Write-Wins).
    for change in changes_by_id.values():
        # Ищем событие глобально по ID (среди всех пользователей),
        # чтобы предотвратить UniqueViolationError при смене аккаунта на клиенте.
        existing_event = await db.scalar(
            select(Event).where(Event.id == change.id)
        )
        if existing_event is None:
            # Записи нет — вставляем как новую, сохраняя клиентский updated_at.
            db.add(
                Event(
                    id=change.id,
                    user_id=user_id,
                    title=change.title,
                    event_type=change.event_type.value,
                    start_time=change.start_time,
                    end_time=change.end_time,
                    location=change.location,
                    teacher=change.teacher,
                    description=change.description,
                    recurrence_rule=change.recurrence_rule,
                    updated_at=change.updated_at,
                    is_deleted=change.is_deleted,
                )
            )
            accepted_ids.add(change.id)
        elif existing_event.user_id != user_id:
            # Событие принадлежит другому пользователю.
            # Безопасно пропускаем, чтобы не ронять синк всего батча.
            continue
        elif change.updated_at > _as_utc(existing_event.updated_at):
            # Событие текущего пользователя и клиент новее — перезаписываем все поля.
            _apply_changes(existing_event, change)
            accepted_ids.add(change.id)
        # Иначе серверная версия новее — клиентское изменение игнорируется,
        # актуальная версия вернётся клиенту в server_changes.

    # 3. Формируем server_changes: всё, что изменилось на сервере
    #    после last_sync (или все активные события при первичном синке).
    query = select(Event).where(Event.user_id == user_id)
    if last_sync is None:
        query = query.where(Event.is_deleted.is_(False))
    else:
        query = query.where(Event.updated_at > last_sync)
    query = query.order_by(Event.updated_at.asc())

    result = await db.scalars(query)
    server_changes = [
        event for event in result.all() if event.id not in accepted_ids
    ]

    # 4. Единый коммит транзакции.
    await db.commit()

    return SyncResponse(
        sync_timestamp=server_sync_time,
        server_changes=[EventResponse.model_validate(e) for e in server_changes],
    )
