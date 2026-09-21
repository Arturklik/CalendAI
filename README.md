# CalendAI

Офлайн-первый календарь расписания: конвертирует фото и скриншоты расписания
(а также текстовые и голосовые сообщения) в события календаря через внешние AI API
(DeepSeek / Vision API / Whisper), хранит всё локально в SQLite и позволяет
редактировать события вручную.

Репозиторий состоит из трёх частей:

| Часть | Стек | Назначение |
|---|---|---|
| **Мобильный клиент** (`lib/`) | Flutter (Android / iOS), SQLite (sqflite) | Офлайн-календарь, локальное хранилище, синхронизация |
| **Backend** (`backend/`) | FastAPI (async), PostgreSQL, SQLAlchemy 2.0, aiogram 3 | REST API, JWT-аутентификация, LWW-синхронизация, Telegram-бот |
| **AI-модуль** (`ai_module/`) | Python 3.10+, Pydantic v2, OpenAI SDK | Распознавание расписаний через OpenAI-совместимый Vision API |

## Мобильный клиент

- Полностью офлайн-первый: приложение работает без интернета; сеть — только
  за интерфейсом `SyncRepository`.
- Дифференциальная синхронизация: `HttpSyncRepository` → `POST /api/v1/sync`
  (Last-Write-Wins, soft-delete). `MockSyncRepository` — для UI-разработки
  без бэкенда.
- Авторизация: JWT в `AuthStorage` (SharedPreferences), вход/регистрация
  через `AuthDialog`, профиль с email и выход из аккаунта в AppBar
  (с очисткой локальной БД при смене пользователя).
- Адрес API — `ApiConfig`: Android-эмулятор `10.0.2.2:8000`, iOS/desktop
  `127.0.0.1:8000`, кастомный IP для реального телефона (`setCustomHost`).
- Локальное хранилище SQLite: таблица `events`, диапазонные запросы, upsert,
  мягкое удаление (soft delete), полная очистка при выходе из аккаунта.
- Экран календаря: месячная сетка с точками-индикаторами типов занятий,
  заголовок дня («Сегодня, 20 сентября» / «Расписание на 21 сентября,
  понедельник»), информативные карточки занятий, модальные детали с
  удалением, ручное создание событий.

### Структура

```
lib/
├── main.dart                       # точка входа
├── models/event.dart               # Event + EventType (канонический контракт)
├── database/app_database.dart      # SQLite-слой (синглтон)
├── repositories/
│   ├── sync_repository.dart        # интерфейс синхронизации
│   ├── http_sync_repository.dart   # синхронизация с backend API
│   └── mock_sync_repository.dart   # мок для UI-разработки без бэкенда
├── services/
│   ├── api_config.dart             # базовый URL API (платформенный/кастомный)
│   ├── api_exceptions.dart         # типизированные ошибки API
│   └── auth_storage.dart           # JWT в SharedPreferences, login/register
├── theme/event_type_style.dart     # цвета и подписи типов занятий
├── utils/                          # форматирование дат, фильтр событий дня
├── widgets/                        # диалоги, карточки, шторки (auth, event)
└── screens/calendar_screen.dart    # экран календаря
```

### Запуск

```bash
flutter pub get
flutter create --platforms=android,ios,macos .   # однократно: платформенные папки
flutter run
```

Для синхронизации поднимите backend (см. [`backend/README.md`](backend/README.md)).
Проверки:

```bash
flutter analyze
flutter test
```

## Backend

FastAPI-сервис: JWT-аутентификация, дифференциальная синхронизация (LWW),
REST CRUD событий, AI-эндпоинты (`/api/v1/ai/*`) и Telegram-бот (aiogram 3),
который принимает фото/голосовые с расписанием, показывает превью по дням
и сохраняет пары в календарь пользователя.

```bash
docker compose -f backend/docker-compose.yml up --build   # из корня репозитория
```

Локальный запуск без Docker (SQLite/PostgreSQL), тесты и линтер — в
[`backend/README.md`](backend/README.md).

## AI-модуль

`ScheduleParser` принимает изображение расписания или текст, отправляет запрос
в OpenAI-совместимый Vision API и возвращает строго структурированный список
событий (Pydantic v2, Structured Outputs с JSON Schema), готовых к записи
в календарь. Backend импортирует модуль напрямую (`ai_module.ScheduleParser`).

Даты занятий определяются по самому расписанию относительно **опорной даты**
(`base_date` — день отправки сообщения): день недели («Понедельник») →
ближайшая дата с этим днём недели; явная дата («21 сентября») → она сама;
если в расписании нет ни дат, ни дней недели → опорная дата.

### Структура

```
ai_module/
├── models.py          # EventType, ParsedCalendarEvent, ScheduleParseResponse
├── parser.py          # ScheduleParser + системный промпт + strict JSON Schema
├── cli.py             # тестовый CLI с табличным выводом
├── requirements.txt
└── .env.example       # шаблон конфигурации
```

### Запуск

```bash
cd ai_module
python -m venv .venv && source .venv/bin/activate   # Python 3.10+
pip install -r requirements.txt
cp .env.example .env    # вписать ключ провайдера (DeepSeek / OpenRouter / OpenAI)

python cli.py --image schedule.png --date 2026-09-20   # --date: опорная дата
python cli.py --text "Понедельник: 1 пара Матанализ, ауд. 214" --date 2026-09-20
python cli.py --image schedule.png --date 2026-09-20 --tz +03:00
```

Конфигурация через `.env` (см. `.env.example`):

```
CALENDAI_API_KEY=sk-...                      # ключ провайдера (обязательно)
CALENDAI_BASE_URL=https://api.deepseek.com   # или api.openai.com / openrouter.ai
CALENDAI_MODEL=gpt-4o-mini                   # vision-модель для изображений
```

## Канонический контракт события

Каждое событие в системе соответствует единой схеме (см. `AGENTS.md`):

| Поле | Тип | Описание |
|---|---|---|
| `id` | String (UUIDv4) | первичный ключ |
| `title` | String | название занятия/события |
| `event_type` | String | `lecture` \| `practice` \| `lab` \| `exam` \| `other` |
| `start_time` | String (ISO 8601 с таймзоной) | `2026-09-08T09:00:00+07:00` |
| `end_time` | String (ISO 8601 с таймзоной) | `2026-09-08T10:35:00+07:00` |
| `location` | String? | аудитория или ссылка |
| `teacher` | String? | ФИО преподавателя |
| `description` | String? | дополнительные заметки |
| `recurrence_rule` | String? | RFC 5545 RRULE, напр. `FREQ=WEEKLY;INTERVAL=2` |
| `updated_at` | String (ISO 8601 UTC) | метка последнего изменения |
| `is_deleted` | Boolean | флаг мягкого удаления |

## Разработка

Правила проекта для AI-агентов и разработчиков — в [`AGENTS.md`](AGENTS.md)
(офлайн-первый подход, интерфейсы вместо прямой привязки к сети,
защитная типизация nullable-полей, минимум зависимостей).

Проверки перед коммитом:

```bash
flutter analyze && flutter test        # мобильный клиент
cd backend && pytest -q                # backend
ruff check backend ai_module           # Python-линтер (из корня, конфиг ruff.toml)
```
