# CalendAI Backend

Server side of CalendAI: an async FastAPI service with PostgreSQL, JWT
authentication, differential synchronization (Last-Write-Wins), a Telegram bot
(aiogram 3), and direct integration with the AI timetable recognition module.

## Stack

- Python 3.10+, FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic
- Pydantic v2 / pydantic-settings
- JWT (python-jose) + bcrypt (passlib)
- aiogram 3.x (polling or webhook, running in the same process as the API)
- Direct import of `ai_module.ScheduleParser` from the monorepo root

## Project structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app, CORS, routers, lifespan (bot)
│   ├── config.py          # Pydantic Settings (.env)
│   ├── database.py        # async engine, sessionmaker, Base, get_db
│   ├── db_types.py        # UTCDateTime — timezone-aware UTC on any DB
│   ├── models/            # User, Event (AGENTS.md contract)
│   ├── schemas/           # auth / event / sync (Pydantic v2)
│   ├── api/               # auth, events, sync, ai routers + deps
│   ├── services/          # auth_service, sync_service (LWW), ai_service
│   └── bot/bot.py         # aiogram 3: photo/voice -> AI -> preview -> save
├── tests/                 # pytest + pytest-asyncio + httpx (SQLite in-memory)
├── alembic/               # migrations
├── Dockerfile             # built from the MONOREPO ROOT
├── docker-compose.yml     # postgres:16-alpine + backend
├── requirements.txt
└── .env.example
```

## Quick start (Docker)

Build and run from the **monorepo root** (the image includes both `backend/`
and `ai_module/`):

```bash
docker compose -f backend/docker-compose.yml up --build
```

The API is exposed at `http://localhost:8000` (docs: `/docs`, health: `/health`).
Alembic migrations are applied automatically on container startup.

Environment variables can be supplied via `backend/.env` (see `.env.example`)
or the shell environment: `JWT_SECRET_KEY`, `CALENDAI_API_KEY`,
`CALENDAI_BASE_URL`, `CALENDAI_MODEL`, `TELEGRAM_BOT_TOKEN`, `BOT_MODE`.

## Local development

Python 3.10+ is required. Option A — system interpreter:

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Option B — project-local isolated Python (if no system 3.10+ is available;
`.tools/` and `.python/` are gitignored and independent of the system
environment):

```bash
cd backend
mkdir -p .tools
curl -sSL https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz \
  | tar -xz -C .tools --strip-components=1        # macOS ARM; use the matching uv archive on other platforms
UV_PYTHON_INSTALL_DIR="$PWD/.python" .tools/uv venv .venv --python 3.12
UV_PYTHON_INSTALL_DIR="$PWD/.python" .tools/uv pip install \
  --python .venv/bin/python -r requirements.txt
```

Then, for either option:

```bash
cp .env.example .env          # fill in JWT_SECRET_KEY, CALENDAI_API_KEY, ...

# Database: PostgreSQL from compose, or SQLite for a quick start —
#   DATABASE_URL=sqlite+aiosqlite:///./calendai.db in .env
docker compose -f docker-compose.yml up db -d

alembic upgrade head          # migrations
uvicorn app.main:app --port 8000   # API + Telegram bot (polling)
```

`ai_module` is imported from the monorepo root: `app/__init__.py`
automatically adds the repository root to `sys.path` for local runs
(in Docker this is handled by `PYTHONPATH=/app`).

> For background runs, redirect the log to a file:
> `nohup .venv/bin/uvicorn app.main:app --port 8000 > .uvicorn.log 2>&1 &`

## Tests and linting

```bash
cd backend
pytest -q                       # tests (SQLite in-memory, no PostgreSQL needed)

cd ..                           # from the repository root
ruff check backend ai_module    # linter (config: ruff.toml at the repo root)
```

Test coverage: registration/login/JWT and password changes, event CRUD and batch
creation, image/text/voice AI parsing routes, initial and incremental
synchronization, LWW conflict resolution, soft-delete propagation,
`ScheduleParser` prompts (base date), and Telegram bot preview formatting
(per-day grouping).

## API (v1, prefix `/api/v1`)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Registration (201 / 409) |
| POST | `/auth/login` | Login, issues a JWT Bearer token |
| GET | `/auth/me` | Current user profile |
| POST | `/auth/change-password` | Verify the current password and set a new one |
| POST | `/auth/telegram-link-token` | Token for `/start <token>` in the bot |
| GET/POST | `/events` | List (with filters) / create |
| POST | `/events/batch` | Create multiple events in one transaction |
| GET/PATCH/DELETE | `/events/{id}` | Read / partial update / soft delete |
| POST | `/sync` | Differential synchronization (LWW) |
| POST | `/ai/parse-image` | Timetable recognition from an image |
| POST | `/ai/parse-voice` | Audio transcription and timetable recognition |
| POST | `/ai/parse-text` | Timetable recognition from text |

AI endpoints accept `base_date` — the **reference date** (the day the message
was sent) — and `tz` (UTC offset, defaults to `+07:00`). The model derives
event dates from the timetable itself: a weekday name maps to the nearest
matching date on or after the base date; an explicit date is used as-is; if
neither is present, the base date is used.

### Synchronization (`POST /api/v1/sync`)

```json
{
  "last_sync_timestamp": "2026-09-08T12:00:00Z",  // null on the initial sync
  "client_changes": [ /* EventSyncItem: full event contract */ ]
}
```

Response:

```json
{
  "sync_timestamp": "2026-09-19T10:00:00Z",
  "server_changes": [ /* events changed on the server, including is_deleted */ ]
}
```

Algorithm (single transaction): a client change is applied if the record does
not exist (INSERT preserving the client `updated_at`) or if the client
`updated_at` is newer than the server one (UPDATE of all fields, including
`is_deleted`). The response contains events with
`updated_at > last_sync_timestamp` (`null` returns all active events), excluding
the events just accepted from this client.

## Telegram bot

1. The user requests a link token: `POST /api/v1/auth/telegram-link-token`.
2. In Telegram: `/start <link_token>` — the account is linked.
3. A timetable photo (or voice message) → recognition via `ai_module` →
   a per-day preview with inline buttons “✅ Add all to calendar” / “❌ Cancel”.
4. Confirmation persists the events (`is_deleted=False`) — they appear in the
   mobile app on the next synchronization.

Modes: `BOT_MODE=polling` (default, a background task in the FastAPI lifespan)
or `BOT_MODE=webhook` (+ `WEBHOOK_URL`, `WEBHOOK_SECRET`; updates are received
at `POST /tg/webhook`).

> **Important:** only one poller may run per `TELEGRAM_BOT_TOKEN`. Do not run a
> local `uvicorn` and the Docker container at the same time when both have the
> token configured: Telegram will split updates between them
> (`TelegramConflictError: terminated by other getUpdates request`), and the bot
> will only see a subset of messages (`/start` and photos may even land in
> different databases). Stop the first instance before starting the second:
> `docker compose -f backend/docker-compose.yml stop backend` or `Ctrl+C` in
> the terminal running `uvicorn`.
