from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Event, EventType, SyncLog, User, new_uuid, utcnow
from app.schemas import CalendarEvent, EventCreate, EventUpdate, ParsedEventIn


def event_to_schema(event: Event) -> CalendarEvent:
    return CalendarEvent.model_validate(event)


def create_event(db: Session, user: User, payload: EventCreate) -> Event:
    event = Event(
        id=str(payload.id) if payload.id else new_uuid(),
        user_id=user.id,
        title=payload.title,
        event_type=payload.event_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        teacher=payload.teacher,
        description=payload.description,
        recurrence_rule=payload.recurrence_rule,
        updated_at=utcnow(),
        is_deleted=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_events_from_parsed(
    db: Session,
    user: User,
    parsed: list[ParsedEventIn],
) -> list[Event]:
    created: list[Event] = []
    now = utcnow()
    for item in parsed:
        event = Event(
            id=new_uuid(),
            user_id=user.id,
            title=item.title,
            event_type=item.event_type,
            start_time=item.start_time,
            end_time=item.end_time,
            location=item.location,
            teacher=item.teacher,
            description=item.description,
            updated_at=now,
            is_deleted=False,
        )
        db.add(event)
        created.append(event)
    db.commit()
    for event in created:
        db.refresh(event)
    return created


def list_events(
    db: Session,
    user: User,
    *,
    include_deleted: bool = False,
) -> list[Event]:
    query = db.query(Event).filter(Event.user_id == user.id)
    if not include_deleted:
        query = query.filter(Event.is_deleted.is_(False))
    return query.order_by(Event.start_time.asc()).all()


def get_event_for_user(db: Session, user: User, event_id: UUID) -> Optional[Event]:
    return (
        db.query(Event)
        .filter(Event.id == str(event_id), Event.user_id == user.id)
        .first()
    )


def update_event(db: Session, event: Event, payload: EventUpdate) -> Event:
    data = payload.model_dump(exclude_unset=True)
    start_time = data.get("start_time", event.start_time)
    end_time = data.get("end_time", event.end_time)
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )
    for key, value in data.items():
        setattr(event, key, value)
    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)
    return event


def soft_delete_event(db: Session, event: Event) -> Event:
    event.is_deleted = True
    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)
    return event


def _normalize_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def apply_client_change(db: Session, user: User, change: CalendarEvent) -> Event:
    existing = (
        db.query(Event)
        .filter(Event.id == str(change.id), Event.user_id == user.id)
        .first()
    )
    change_updated = _normalize_dt(change.updated_at)

    if existing is None:
        event = Event(
            id=str(change.id),
            user_id=user.id,
            title=change.title,
            event_type=EventType(change.event_type),
            start_time=change.start_time,
            end_time=change.end_time,
            location=change.location,
            teacher=change.teacher,
            description=change.description,
            recurrence_rule=change.recurrence_rule,
            updated_at=change_updated,
            is_deleted=change.is_deleted,
        )
        db.add(event)
        return event

    existing_updated = _normalize_dt(existing.updated_at)
    # Arthur contract: Last-Write-Wins only if client.updated_at > db.updated_at.
    if change_updated > existing_updated:
        existing.title = change.title
        existing.event_type = EventType(change.event_type)
        existing.start_time = change.start_time
        existing.end_time = change.end_time
        existing.location = change.location
        existing.teacher = change.teacher
        existing.description = change.description
        existing.recurrence_rule = change.recurrence_rule
        existing.updated_at = change_updated
        existing.is_deleted = change.is_deleted
    return existing


def sync_events(
    db: Session,
    user: User,
    *,
    last_sync_timestamp: Optional[datetime],
    client_changes: list[CalendarEvent],
    device_id: Optional[str] = None,
) -> tuple[datetime, list[CalendarEvent]]:
    for change in client_changes:
        apply_client_change(db, user, change)

    db.flush()

    query = db.query(Event).filter(Event.user_id == user.id)
    if last_sync_timestamp is not None:
        query = query.filter(Event.updated_at > _normalize_dt(last_sync_timestamp))

    server_rows = query.order_by(Event.updated_at.asc()).all()
    server_changes = [event_to_schema(row) for row in server_rows]

    sync_ts = utcnow()
    log = (
        db.query(SyncLog)
        .filter(SyncLog.user_id == user.id, SyncLog.device_id == device_id)
        .first()
    )
    if log is None:
        log = SyncLog(user_id=user.id, device_id=device_id)
        db.add(log)

    log.last_sync_at = sync_ts
    log.client_changes_count = len(client_changes)
    log.server_changes_count = len(server_changes)

    db.commit()
    return sync_ts, server_changes
