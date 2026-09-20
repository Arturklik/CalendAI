# CalendAI Backend

Серверная часть CalendAI: асинхронный FastAPI-сервис с PostgreSQL,
JWT-аутентификацией, дифференциальной синхронизацией (Last-Write-Wins),
Telegram-ботом (aiogram 3) и интеграцией AI-модуля распознавания расписаний.

## Стек

- Python 3.10+, FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic
- Pydantic v2 / pydantic-settings
- JWT (python-jose) + bcrypt (passlib)
- aiogram 3.x (polling или webhook, в том же процессе, что и API)
- Прямой импорт `ai_module.ScheduleParser` из корня монорепозитория

## Структура

```
backend/
├── app/
│   ├── main.py            # FastAPI, CORS, роутеры, lifespan (бот)
│   ├── config.py          # Pydantic Settings (.env)
│   ├── database.py        # Async engine, sessionmaker, Base, get_db
│   ├── db_types.py        # UTCDateTime — aware-UTC на любой СУБД
│   ├── models/            # User, Event (контракт AGENTS.md)
│   ├── schemas/           # auth / event / sync (Pydantic v2)
│   ├── api/               # auth, events, sync, ai роутеры + deps
│   ├── services/          # auth_service, sync_service (LWW), ai_service
│   └── bot/bot.py         # aiogram 3: фото/войс -> AI -> превью -> save
├── tests/                 # pytest + pytest-asyncio + httpx (SQLite in-memory)
├── alembic/               # миграции
├── Dockerfile             # сборка из КОРНЯ монорепозитория
├── docker-compose.yml     # postgres:16-alpine + backend
├── requirements.txt
└── .env.example
```

## Быстрый старт (Docker)

Сборка и запуск ведутся из **корня монорепозитория** (в образ копируется и
`backend/`, и `ai_module/`):

```bash
docker compose -f backend/docker-compose.yml up --build
```

API поднимется на `http://localhost:8000` (docs: `/docs`, health: `/health`).
Миграции применяются автоматически при старте контейнера.

Переменные окружения можно передать через `backend/.env` (см. `.env.example`)
или окружение shell: `JWT_SECRET_KEY`, `CALENDAI_API_KEY`, `CALENDAI_BASE_URL`,
`CALENDAI_MODEL`, `TELEGRAM_BOT_TOKEN`, `BOT_MODE`.

## Локальная разработка

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # заполнить JWT_SECRET_KEY, CALENDAI_API_KEY, ...

# PostgreSQL (или поднимите только БД из compose):
docker compose -f docker-compose.yml up db -d

alembic upgrade head          # миграции
uvicorn app.main:app --reload # API + Telegram-бот (polling)
```

`ai_module` импортируется из корня монорепозитория: `app/__init__.py`
автоматически добавляет корень репозитория в `sys.path` при локальном запуске
(в Docker это делает `PYTHONPATH=/app`).

## Тесты

```bash
cd backend
pytest -q
```

Тесты используют SQLite in-memory (aiosqlite, StaticPool) и не требуют
PostgreSQL: регистрация/логин/JWT, CRUD событий, первичная и вторичная
синхронизация, разрешение конфликтов LWW, распространение soft-delete.

## API (v1, префикс `/api/v1`)

| Метод | Путь | Описание |
|---|---|---|
| POST | `/auth/register` | Регистрация (201 / 409) |
| POST | `/auth/login` | Вход, выдача JWT Bearer |
| GET | `/auth/me` | Профиль текущего пользователя |
| POST | `/auth/telegram-link-token` | Токен для `/start <token>` в боте |
| GET/POST | `/events` | Список (с фильтрами) / создание |
| GET/PATCH/DELETE | `/events/{id}` | Чтение / частичное обновление / soft delete |
| POST | `/sync` | Дифференциальная синхронизация (LWW) |
| POST | `/ai/parse-image` | Распознавание расписания с изображения |
| POST | `/ai/parse-text` | Распознавание расписания из текста |

### Синхронизация (`POST /api/v1/sync`)

```json
{
  "last_sync_timestamp": "2026-09-08T12:00:00Z",  // null при первичном синке
  "client_changes": [ /* EventSyncItem: полный контракт события */ ]
}
```

Ответ:

```json
{
  "sync_timestamp": "2026-09-19T10:00:00Z",
  "server_changes": [ /* события, изменённые на сервере, включая is_deleted */ ]
}
```

Алгоритм (одна транзакция): клиентское изменение применяется, если запись
отсутствует (INSERT с клиентским `updated_at`) либо клиентский `updated_at`
новее серверного (UPDATE всех полей, включая `is_deleted`). В ответ
возвращаются события с `updated_at > last_sync_timestamp` (при `null` — все
активные), за исключением только что принятых от этого клиента.

## Telegram-бот

1. Пользователь получает токен: `POST /api/v1/auth/telegram-link-token`.
2. В Telegram: `/start <link_token>` — аккаунт привязан.
3. Фото расписания (или голосовое) → распознавание через `ai_module` →
   превью занятий с кнопками «✅ Добавить все в календарь» / «❌ Отмена».
4. Подтверждение сохраняет события в БД (`is_deleted=False`) — при
   следующей синхронизации они появятся в мобильном приложении.

Режимы: `BOT_MODE=polling` (по умолчанию, фоновая задача в lifespan) или
`BOT_MODE=webhook` (+ `WEBHOOK_URL`, `WEBHOOK_SECRET`; приём обновлений на
`POST /tg/webhook`).
