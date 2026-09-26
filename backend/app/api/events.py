"""REST CRUD для событий: /api/v1/events (веб-интерфейс).

Мобильный клиент работает через /api/v1/sync, эти эндпоинты — для
прямого управления событиями (веб/админка). Каждая мутация обновляет
`updated_at` серверным временем UTC, чтобы изменения корректно
разлетались по клиентам при следующей синхронизации.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.event import Event
from ..models.user import User
from ..schemas.event import EventCreate, EventResponse, EventUpdate
from .deps import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


def _touch() -> datetime:
    return datetime.now(timezone.utc)


async def _get_owned_event(
    db: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
) -> Event:
    event = await db.scalar(
        select(Event).where(Event.id == event_id, Event.user_id == user_id)
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Событие не найдено"
        )
    return event


@router.get("", response_model=list[EventResponse])
async def list_events(
    start: datetime | None = Query(default=None, description="Начало диапазона (ISO 8601)"),
    end: datetime | None = Query(default=None, description="Конец диапазона (ISO 8601)"),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Event]:
    """Список событий пользователя, опционально — в диапазоне дат."""
    query = select(Event).where(Event.user_id == current_user.id)
    if not include_deleted:
        query = query.where(Event.is_deleted.is_(False))
    if start is not None:
        query = query.where(Event.end_time > start)
    if end is not None:
        query = query.where(Event.start_time < end)
    query = query.order_by(Event.start_time.asc())
    result = await db.scalars(query)
    return list(result.all())


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    """Создание события."""
    event_id = data.id or uuid.uuid4()
    existing = await db.scalar(
        select(Event.id).where(
            Event.id == event_id, Event.user_id == current_user.id
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Событие с таким id уже существует",
        )
    event = Event(
        id=event_id,
        user_id=current_user.id,
        title=data.title,
        event_type=data.event_type.value,
        start_time=data.start_time,
        end_time=data.end_time,
        location=data.location,
        teacher=data.teacher,
        description=data.description,
        recurrence_rule=data.recurrence_rule,
        updated_at=_touch(),
        is_deleted=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.post(
    "/batch",
    response_model=list[EventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_events_batch(
    events: list[EventCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Event]:
    """Создаёт набор событий одной транзакцией."""
    event_ids = [data.id or uuid.uuid4() for data in events]
    if len(set(event_ids)) != len(event_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="В запросе повторяются id событий",
        )

    if event_ids:
        existing_ids = await db.scalars(
            select(Event.id).where(Event.id.in_(event_ids))
        )
        if existing_ids.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Событие с таким id уже существует",
            )

    updated_at = _touch()
    created_events = [
        Event(
            id=event_id,
            user_id=current_user.id,
            title=data.title,
            event_type=data.event_type.value,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location,
            teacher=data.teacher,
            description=data.description,
            recurrence_rule=data.recurrence_rule,
            updated_at=updated_at,
            is_deleted=False,
        )
        for data, event_id in zip(events, event_ids, strict=True)
    ]
    db.add_all(created_events)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать события с указанными id",
        ) from exc

    return created_events


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    """Получение события по id."""
    return await _get_owned_event(db, event_id, current_user.id)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    """Частичное обновление события."""
    event = await _get_owned_event(db, event_id, current_user.id)

    updates = data.model_dump(exclude_unset=True)
    # NOT NULL-поля контракта нельзя обнулить через PATCH.
    for field in ("title", "event_type", "start_time", "end_time"):
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"Поле {field} не может быть null",
            )
    if "event_type" in updates:
        updates["event_type"] = updates["event_type"].value
    for field, value in updates.items():
        setattr(event, field, value)

    # Инвариант контракта: end_time > start_time.
    if event.end_time <= event.start_time:
        raise HTTPException(
            status_code=422,
            detail="end_time должен быть позже start_time",
        )

    event.updated_at = _touch()
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Мягкое удаление: запись остаётся для распространения по клиентам."""
    event = await _get_owned_event(db, event_id, current_user.id)
    event.is_deleted = True
    event.updated_at = _touch()
    await db.commit()
