"""Модели данных AI-модуля CalendAI (Pydantic v2).

Соответствуют каноническому контракту события из AGENTS.md.
Служебные поля контракта (id, recurrence_rule, updated_at, is_deleted)
здесь отсутствуют — их заполняет клиент при записи в календарь.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EventType(str, Enum):
    lecture = "lecture"
    practice = "practice"
    lab = "lab"
    exam = "exam"
    other = "other"


class ParsedCalendarEvent(BaseModel):
    """Занятие, распознанное из расписания."""

    title: str = Field(min_length=1, max_length=200)
    event_type: EventType
    start_time: datetime  # ISO 8601, обязательно с часовым поясом
    end_time: datetime  # ISO 8601, обязательно с часовым поясом
    location: Optional[str] = None
    teacher: Optional[str] = None
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include timezone offset (ISO 8601)")
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> "ParsedCalendarEvent":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleParseResponse(BaseModel):
    """Ответ парсера: список распознанных занятий."""

    events: list[ParsedCalendarEvent]
