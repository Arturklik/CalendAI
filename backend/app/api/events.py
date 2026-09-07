from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import CalendarEvent, EventCreate, EventUpdate
from app.security import get_current_user
from app.services import events as event_service

router = APIRouter(prefix="/events", tags=["events"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[CalendarEvent])
def list_events(current_user: CurrentUser, db: DbSession) -> list[CalendarEvent]:
    rows = event_service.list_events(db, current_user)
    return [event_service.event_to_schema(row) for row in rows]


@router.post("", response_model=CalendarEvent, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CalendarEvent:
    if payload.id is not None:
        existing = event_service.get_event_for_user(db, current_user, payload.id)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event already exists")
    event = event_service.create_event(db, current_user, payload)
    return event_service.event_to_schema(event)


@router.get("/{event_id}", response_model=CalendarEvent)
def get_event(event_id: UUID, current_user: CurrentUser, db: DbSession) -> CalendarEvent:
    event = event_service.get_event_for_user(db, current_user, event_id)
    if event is None or event.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event_service.event_to_schema(event)


@router.patch("/{event_id}", response_model=CalendarEvent)
def update_event(
    event_id: UUID,
    payload: EventUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> CalendarEvent:
    event = event_service.get_event_for_user(db, current_user, event_id)
    if event is None or event.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = event_service.update_event(db, event, payload)
    return event_service.event_to_schema(event)


@router.delete("/{event_id}", response_model=CalendarEvent)
def delete_event(event_id: UUID, current_user: CurrentUser, db: DbSession) -> CalendarEvent:
    event = event_service.get_event_for_user(db, current_user, event_id)
    if event is None or event.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = event_service.soft_delete_event(db, event)
    return event_service.event_to_schema(event)
