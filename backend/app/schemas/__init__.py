from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import EventType, SubscriptionPlan


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include timezone (ISO 8601 with offset)")
    return value


class CalendarEvent(BaseModel):
    """Shared event payload for mobile, web, Telegram, and PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str = Field(min_length=1, max_length=512)
    event_type: EventType = EventType.OTHER
    start_time: datetime
    end_time: datetime
    location: Optional[str] = Field(default=None, max_length=255)
    teacher: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    recurrence_rule: Optional[str] = None
    updated_at: datetime
    is_deleted: bool = False

    @field_validator("start_time", "end_time", "updated_at")
    @classmethod
    def require_tz(cls, value: datetime) -> datetime:
        return _ensure_timezone(value)

    @model_validator(mode="after")
    def end_after_start(self) -> "CalendarEvent":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventCreate(BaseModel):
    id: Optional[UUID] = None
    title: str = Field(min_length=1, max_length=512)
    event_type: EventType = EventType.OTHER
    start_time: datetime
    end_time: datetime
    location: Optional[str] = Field(default=None, max_length=255)
    teacher: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    recurrence_rule: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_tz(cls, value: datetime) -> datetime:
        return _ensure_timezone(value)

    @model_validator(mode="after")
    def end_after_start(self) -> "EventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    event_type: Optional[EventType] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    teacher: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    recurrence_rule: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_tz(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return value
        return _ensure_timezone(value)


class SyncRequest(BaseModel):
    last_sync_timestamp: Optional[datetime] = None
    client_changes: list[CalendarEvent] = Field(default_factory=list)

    @field_validator("last_sync_timestamp")
    @classmethod
    def require_tz(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return value
        return _ensure_timezone(value)


class SyncResponse(BaseModel):
    sync_timestamp: datetime
    server_changes: list[CalendarEvent]


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TelegramUpsert(BaseModel):
    telegram_id: int
    display_name: Optional[str] = Field(default=None, max_length=255)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: Optional[EmailStr] = None
    telegram_id: Optional[int] = None
    display_name: Optional[str] = None
    timezone: str
    subscription_tier: SubscriptionPlan
    ai_requests_this_week: int
    week_reset_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ParsedEventIn(BaseModel):
    title: str
    event_type: EventType = EventType.OTHER
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    teacher: Optional[str] = None
    description: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_tz(cls, value: datetime) -> datetime:
        return _ensure_timezone(value)


class AIParseResponse(BaseModel):
    events: list[ParsedEventIn]


class AIParseTextRequest(BaseModel):
    text: str = Field(min_length=1)
    target_date: Optional[datetime] = None


class AIConfirmRequest(BaseModel):
    events: list[ParsedEventIn]
