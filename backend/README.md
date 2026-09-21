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

Нужен Python 3.10+. Вариант А — системный интерпретатор:

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Вариант Б — изолированный Python внутри проекта (если системного 3.10+ нет;
`.tools/` и `.python/` в `.gitignore` и не зависят от системного окружения):

```bash
cd backend
mkdir -p .tools
curl -sSL https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz \
  | tar -xz -C .tools --strip-components=1        # macOS ARM; для других платформ — свой архив uv
UV_PYTHON_INSTALL_DIR="$PWD/.python" .tools/uv venv .venv --python 3.12
UV_PYTHON_INSTALL_DIR="$PWD/.python" .tools/uv pip install \
  --python .venv/bin/python -r requirements.txt
```

Далее (для любого варианта):

```bash
cp .env.example .env          # заполнить JWT_SECRET_KEY, CALENDAI_API_KEY, ...

# БД: PostgreSQL из compose либо SQLite для быстрого старта —
#   DATABASE_URL=sqlite+aiosqlite:///./calendai.db в .env
docker compose -f docker-compose.yml up db -d

alembic upgrade head          # миграции
uvicorn app.main:app --port 8000   # API + Telegram-бот (polling)
```

`ai_module` импортируется из корня монорепозитория: `app/__init__.py`
автоматически добавляет корень репозитория в `sys.path` при локальном запуске
(в Docker это делает `PYTHONPATH=/app`).

> При запуске в фоне удобно писать лог в файл:
> `nohup .venv/bin/uvicorn app.main:app --port 8000 > .uvicorn.log 2>&1 &`

## Тесты и линтер

```bash
cd backend
pytest -q                       # тесты (SQLite in-memory, без PostgreSQL)

cd ..                           # из корня репозитория
ruff check backend ai_module    # линтер (конфиг ruff.toml в корне)
```

Тесты покрывают: регистрация/логин/JWT, CRUD событий, первичную и вторичную
синхронизацию, разрешение конфликтов LWW, распространение soft-delete,
промпты `ScheduleParser` (опорная дата) и форматирование превью расписания
в Telegram-боте (группировка по дням недели).

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

AI-эндпоинты принимают `base_date` — **опорную дату** (день отправки
сообщения) и `tz` (смещение, по умолчанию `+07:00`). Даты занятий модель
выводит из самого расписания: день недели → ближайшая дата с этим днём
недели, начиная с опорной; явная дата → она сама; если дат и дней недели
нет → опорная дата.

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

> **Важно:** с одним `TELEGRAM_BOT_TOKEN` одновременно может работать только
> один poller. Не запускайте локальный `uvicorn` и Docker-контейнер
> одновременно, если у обоих задан токен: Telegram начнёт раскидывать апдейты
> между ними (`TelegramConflictError: terminated by other getUpdates request`),
> и бот будет «видеть» только часть сообщений (а `/start` и фото могут попасть
> в разные базы данных). Перед запуском второго экземпляра остановите первый:
> `docker compose -f backend/docker-compose.yml stop backend` или `Ctrl+C`
> в терминале с `uvicorn`.
