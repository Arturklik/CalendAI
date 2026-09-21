"""Схемы событий — зеркало канонического контракта AGENTS.md
и `lib/models/event.dart` (snake_case, ISO 8601 с таймзоной)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    """Тип события по каноническому контракту."""

    lecture = "lecture"
    practice = "practice"
    lab = "lab"
    exam = "exam"
    other = "other"


def _to_utc(value: datetime) -> datetime:
    """Нормализация к aware-datetime в UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone offset (ISO 8601)")
    return value.astimezone(timezone.utc)


class EventBase(BaseModel):
    """Общие поля события с инвариантами контракта."""

    title: str = Field(min_length=1, max_length=200)
    event_type: EventType
    start_time: datetime
    end_time: datetime
    location: str | None = Field(default=None, max_length=255)
    teacher: str | None = Field(default=None, max_length=255)
    description: str | None = None
    recurrence_rule: str | None = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> EventBase:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventCreate(EventBase):
    """Создание события через REST CRUD.

    `id` опционален: клиент может передать свой UUIDv4 (как при синке),
    иначе сервер сгенерирует новый.
    """

    id: uuid.UUID | None = None


class EventUpdate(BaseModel):
    """Частичное обновление события (PATCH). Все поля опциональны."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    event_type: EventType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    teacher: str | None = Field(default=None, max_length=255)
    description: str | None = None
    recurrence_rule: str | None = Field(default=None, max_length=255)
    is_deleted: bool | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return _to_utc(value)


class EventResponse(EventBase):
    """Полный канонический контракт события (то, что видит клиент)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    updated_at: datetime
    is_deleted: bool


class EventSyncItem(EventBase):
    """Элемент `client_changes` при синхронизации.

    Клиент всегда присылает событие целиком: id — клиентский UUIDv4,
    updated_at — метка последнего локального изменения (UTC),
    is_deleted — флаг soft delete.
    """

    id: uuid.UUID
    updated_at: datetime
    is_deleted: bool = False

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_utc(cls, value: datetime) -> datetime:
        return _to_utc(value)
