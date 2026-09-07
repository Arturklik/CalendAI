from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def week_reset_at() -> datetime:
    return utcnow() + timedelta(days=7)


def new_uuid() -> str:
    return str(uuid4())


class TZDateTime(TypeDecorator):
    """Store UTC timestamps; always return timezone-aware datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        value = value.astimezone(timezone.utc)
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SubscriptionPlan(str, Enum):
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"


class EventType(str, Enum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    LAB = "lab"
    EXAM = "exam"
    OTHER = "other"


class User(Base):
    """Matches Arthur's users DDL, plus display_name/timezone for the web portal."""

    __tablename__ = "users"
    __table_args__ = (Index("idx_users_telegram_id", "telegram_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    subscription_tier: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(SubscriptionPlan, name="subscription_tier", native_enum=False),
        nullable=False,
        default=SubscriptionPlan.FREE,
    )
    ai_requests_this_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    week_reset_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=week_reset_at)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utcnow)

    events: Mapped[list["Event"]] = relationship(back_populates="user")
    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="user")


class Event(Base):
    """Calendar event — Arthur DDL: events belong to user_id, not a calendars table."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="chk_event_time"),
        Index("idx_events_user_updated", "user_id", "updated_at"),
        Index("idx_events_user_start_time", "user_id", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="event_type", native_enum=False),
        nullable=False,
        default=EventType.OTHER,
    )
    start_time: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    teacher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utcnow, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="events")


class SyncLog(Base):
    __tablename__ = "sync_logs"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_sync_logs_user_device"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_sync_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utcnow)
    client_changes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    server_changes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sync_logs")
