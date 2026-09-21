"""Фикстуры pytest: in-memory SQLite, тестовый HTTP-клиент, хелперы.

БД — SQLite in-memory через aiosqlite со StaticPool (одно соединение
на тест, схема создаётся через Base.metadata.create_all).
Приложение подключается к ней через переопределение зависимости get_db.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

# Импорты приложения требуют backend/ и корня репозитория в sys.path,
# а DATABASE_URL должен быть подставлен ДО импорта app.database.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
for _path in (str(_BACKEND_DIR), str(_REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncGenerator[
    async_sessionmaker[AsyncSession], None
]:
    """Изолированная in-memory БД на каждый тест."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент поверх ASGI-приложения с подменённой БД."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def register_user(
    client: AsyncClient,
) -> Callable[[str, str], Awaitable[dict[str, str]]]:
    """Фабрика: регистрация + логин, возвращает auth-заголовки."""

    async def _make(
        email: str = "user@example.com", password: str = "secret123"
    ) -> dict[str, str]:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert response.status_code == 201, response.text
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture(name="make_event_payload")
def make_event_payload_fixture() -> Callable[..., dict]:
    """Фабрика валидных payload'ов события (канонический контракт)."""

    def _make(**overrides: object) -> dict:
        payload = {
            "id": str(uuid.uuid4()),
            "title": "Математический анализ",
            "event_type": "lecture",
            "start_time": "2026-09-08T09:00:00+07:00",
            "end_time": "2026-09-08T10:35:00+07:00",
            "location": "Ауд. 214",
            "teacher": "Иванов А.П.",
            "description": None,
            "recurrence_rule": "FREQ=WEEKLY;INTERVAL=1",
            "updated_at": "2026-09-08T02:00:00Z",
            "is_deleted": False,
        }
        payload.update(overrides)
        return payload

    return _make
