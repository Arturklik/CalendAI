"""Кастомные типы SQLAlchemy для кросс-диалектной работы с таймзонами."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """DateTime(timezone=True), всегда возвращающий aware-datetime в UTC.

    PostgreSQL TIMESTAMPTZ возвращает aware-datetime нативно, а SQLite —
    naive; декоратор выравнивает поведение: на чтении naive-метка
    трактуется как UTC, aware — приводится к UTC. На записи любое
    значение нормализуется к UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
