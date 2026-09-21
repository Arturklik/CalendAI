# CalendAI

Offline-first schedule calendar. Converts timetable photos/screenshots (and text
or voice messages) into calendar events via external OpenAI-compatible AI APIs
(Vision / Whisper), persists them locally in SQLite, and synchronizes them with
a FastAPI backend.

The monorepo contains three components:

| Component | Stack | Responsibility |
|---|---|---|
| **Mobile client** (`lib/`) | Flutter (Android / iOS), SQLite (sqflite) | Offline-first calendar, local event store, differential sync |
| **Backend** (`backend/`) | FastAPI (async), PostgreSQL, SQLAlchemy 2.0, aiogram 3 | REST API, JWT auth, LWW sync, Telegram bot |
| **AI module** (`ai_module/`) | Python 3.10+, Pydantic v2, OpenAI SDK | Timetable recognition via OpenAI-compatible Vision API |

## Mobile client

- **Offline-first by design**: the app is fully functional without network
  access; all network I/O is isolated behind the `SyncRepository` interface.
- **Differential sync**: `HttpSyncRepository` implements `POST /api/v1/sync`
  with Last-Write-Wins conflict resolution and soft-delete (tombstone)
  propagation. `MockSyncRepository` is available for UI development without
  a running backend.
- **Authentication**: JWT persisted in `SharedPreferences` via `AuthStorage`;
  login/registration through `AuthDialog`; profile with email and sign-out in
  the app bar (the local database is wiped on account switch).
- **API endpoint resolution** via `ApiConfig`: Android emulator →
  `http://10.0.2.2:8000/api/v1`, iOS/desktop → `http://127.0.0.1:8000/api/v1`;
  custom host override for physical devices (`ApiConfig.setCustomHost`).
- **Local storage**: SQLite (`sqflite`), single `events` table, range queries,
  upsert, soft delete, full wipe on sign-out.
- **Calendar UI**: month grid with per-type event indicators, localized day
  header, event cards (type color bar, time range, location, teacher), modal
  details sheet with soft delete, manual event creation via bottom sheet.

### Project structure

```
lib/
├── main.dart                       # entry point
├── models/event.dart               # Event + EventType (canonical contract)
├── database/app_database.dart      # SQLite layer (singleton)
├── repositories/
│   ├── sync_repository.dart        # sync interface
│   ├── http_sync_repository.dart   # backend API implementation
│   └── mock_sync_repository.dart   # mock for UI development without backend
├── services/
│   ├── api_config.dart             # API base URL (platform default / custom)
│   ├── api_exceptions.dart         # typed API errors
│   └── auth_storage.dart           # JWT in SharedPreferences, login/register
├── theme/event_type_style.dart     # event type colors and labels
├── utils/                          # date formatting, per-day event filtering
├── widgets/                        # dialogs, cards, sheets (auth, event)
└── screens/calendar_screen.dart    # calendar screen
```

### Build and run

```bash
flutter pub get
flutter create --platforms=android,ios,macos .   # one-time: generate platform folders
flutter run
```

A running backend is required for synchronization (see
[`backend/README.md`](backend/README.md)). Static analysis and tests:

```bash
flutter analyze
flutter test
```

## Backend

FastAPI service: JWT authentication, differential synchronization (LWW),
event CRUD, AI parsing endpoints (`/api/v1/ai/*`), and a Telegram bot
(aiogram 3) that accepts timetable photos/voice messages, renders a per-day
preview, and persists the recognized classes to the user's calendar.

```bash
docker compose -f backend/docker-compose.yml up --build   # from the repo root
```

Local setup (SQLite/PostgreSQL), tests, and linting: see
[`backend/README.md`](backend/README.md).

## AI module

`ScheduleParser` accepts a timetable image or text, calls an OpenAI-compatible
Vision API, and returns a strictly typed event list (Pydantic v2, Structured
Outputs with JSON Schema) ready for calendar ingestion. The backend imports the
module directly (`ai_module.ScheduleParser`).

Event dates are derived from the timetable itself relative to a **base date**
(`base_date` — the day the message was sent):

- weekday name (`Monday`, `Mon`) → nearest matching date on or after the base
  date;
- explicit date (`Sep 21`, `21.09`) → used as-is (year inferred from the base
  date);
- neither present → the base date is used.

### Project structure

```
ai_module/
├── models.py          # EventType, ParsedCalendarEvent, ScheduleParseResponse
├── parser.py          # ScheduleParser + system prompt + strict JSON Schema
├── cli.py             # test CLI with tabular output
├── requirements.txt
└── .env.example       # configuration template
```

### Usage

```bash
cd ai_module
python -m venv .venv && source .venv/bin/activate   # Python 3.10+
pip install -r requirements.txt
cp .env.example .env    # add the provider API key (DeepSeek / OpenRouter / OpenAI)

python cli.py --image schedule.png --date 2026-09-20   # --date is the base date
python cli.py --text "Monday: 1st period Calculus, room 214" --date 2026-09-20
python cli.py --image schedule.png --date 2026-09-20 --tz +03:00
```

Configuration via `.env` (see `.env.example`):

```
CALENDAI_API_KEY=sk-...                      # provider API key (required)
CALENDAI_BASE_URL=https://api.deepseek.com   # or api.openai.com / openrouter.ai
CALENDAI_MODEL=gpt-4o-mini                   # vision model for images
```

## Canonical event contract

Every event in the system conforms to a single schema (see `AGENTS.md`):

| Field | Type | Description |
|---|---|---|
| `id` | String (UUIDv4) | primary key |
| `title` | String | class/event title |
| `event_type` | String | `lecture` \| `practice` \| `lab` \| `exam` \| `other` |
| `start_time` | String (ISO 8601 with timezone) | `2026-09-08T09:00:00+07:00` |
| `end_time` | String (ISO 8601 with timezone) | `2026-09-08T10:35:00+07:00` |
| `location` | String? | room or link |
| `teacher` | String? | lecturer name |
| `description` | String? | additional notes |
| `recurrence_rule` | String? | RFC 5545 RRULE, e.g. `FREQ=WEEKLY;INTERVAL=2` |
| `updated_at` | String (ISO 8601 UTC) | last modification timestamp |
| `is_deleted` | Boolean | soft-delete flag |

## Development

Project conventions for AI agents and developers live in
[`AGENTS.md`](AGENTS.md) (offline-first, interfaces instead of direct network
coupling, defensive typing for nullable fields, minimal dependencies).

Pre-commit checks:

```bash
flutter analyze && flutter test        # mobile client
cd backend && pytest -q                # backend
ruff check backend ai_module           # Python linter (from repo root, config: ruff.toml)
```
