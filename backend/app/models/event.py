"""Модель календарного события.

Строго зеркалирует канонический контракт AGENTS.md и модель
`lib/models/event.dart` Flutter-клиента:

    id (UUIDv4, генерируется клиентом), user_id, title,
    event_type (lecture|practice|lab|exam|other),
    start_time / end_time (TIMESTAMPTZ, end_time > start_time),
    location / teacher / description (nullable),
    recurrence_rule (RFC 5545, nullable),
    updated_at (TIMESTAMPTZ, всегда UTC), is_deleted (soft delete).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from ..database import Base
from ..db_types import UTCDateTime

EVENT_TYPE_VALUES = ("lecture", "practice", "lab", "exam", "other")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_events_end_after_start"),
        CheckConstraint(
            f"event_type IN {EVENT_TYPE_VALUES}", name="ck_events_event_type"
        ),
        Index("idx_events_user_updated", "user_id", "updated_at"),
        Index("idx_events_user_start_time", "user_id", "start_time"),
    )

    # PK генерирует клиент (UUIDv4) — сервер обязан принимать чужие id.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    teacher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Метка последнего изменения, всегда UTC. Ключевое поле LWW-синхронизации.
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    user: Mapped["User"] = relationship(back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover - отладочный метод
        return f"Event(id={self.id!s}, title={self.title!r})"
