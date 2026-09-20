"""Подключение к PostgreSQL: async engine, session factory, Base.

Используется SQLAlchemy 2.0 (asyncio + asyncpg). Зависимость `get_db`
выдаёт асинхронную сессию на время запроса.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: сессия БД с автозакрытием."""
    async with async_session_factory() as session:
        yield session
