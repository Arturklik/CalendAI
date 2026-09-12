# CalendAI

Календарь пар университета: фото или текст расписания → ИИ → события в календаре. Закрытая бета, без оплаты.

| Модуль | Что делает | Кто | Где |
|---|---|---|---|
| `backend/` | REST API: авторизация, события, дифф-синк, ИИ-эндпоинты, квоты | Антон | FastAPI + SQLAlchemy |
| `web/` | Веб-календарь (отдаётся тем же API-сервером) | Антон | vanilla JS |
| `bot/` | Telegram-бот: ввод расписания фото/текстом | Антон | python-telegram-bot |
| `mobile/` | Flutter-приложение: офлайн-календарь + синк | Артур | Flutter |
| `ai_module/` | Парсер расписаний через Vision API | Артур | Python |
| `backend/contracts/` | Контракты данных — источник правды | общий | JSON Schema |

## Как это работает

1. Пользователь кидает боту **фото или текст расписания** → ИИ распознаёт пары → превью → кнопка «Добавить» → события в БД.
2. Телефон и веб забирают события **дифференциальным синком** `POST /api/v1/sync`.
3. Веб и мобилка — просмотр и ручное редактирование; Telegram — быстрый ввод.

Известное ограничение: аккаунт, созданный ботом (по `telegram_id`), и аккаунт, созданный на сайте (по email), — это пока **разные пользователи**. Привязку запланировали на потом.

## Контракт события

Канонические описания: `backend/contracts/calendar_event.schema.json` и `mobile/AGENTS.md`.

- `id` — UUIDv4, генерирует клиент или сервер (клиент генерирует офлайн).
- `start_time` / `end_time` — ISO 8601, **обязательно с часовым поясом**; `end_time > start_time`.
- Удаление — мягкое: `is_deleted=true`, запись остаётся и разъезжается синком.
- Разрешение конфликтов (LWW): клиентская копия побеждает, только если `client.updated_at > server.updated_at`.

Синк: запрос `{ "last_sync_timestamp": null | ISO, "client_changes": [CalendarEvent] }`, ответ `{ "sync_timestamp", "server_changes": [CalendarEvent] }`.

---

## Запуск backend + web

Нужен Python 3.12+. Postgres не обязателен — локально хватает SQLite.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate            # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # PowerShell: copy .env.example .env
```

В `.env` для локалки достаточно:

```
DATABASE_URL=sqlite:///./calendai.db
```

Запуск:

```bash
uvicorn app.main:app --reload --port 8000
```

- веб-календарь: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- health: http://127.0.0.1:8000/health

В VS Code / Cursor уже лежат конфиги запуска (`.vscode/launch.json`): **CalendAI API**, **CalendAI Telegram bot**, **CalendAI: API + bot**. Интерпретатор — `backend/.venv` (на Windows `backend/.venv/Scripts/python.exe` см. `.vscode/settings.json`).

### Postgres (когда понадобится не только файл)

```bash
cd backend
docker compose up -d
```

И в `.env` укажите postgres-URL из `.env.example`:

```
DATABASE_URL=postgresql+psycopg2://calendai:calendai@localhost:5432/calendai
```

---

## Запуск Telegram-бота

1. [@BotFather](https://t.me/BotFather) → `/newbot` → скопируйте токен.
2. В `backend/.env`:

   ```
   TELEGRAM_BOT_TOKEN=123:AA...
   BOT_API_KEY=dev-bot-key-change-me
   API_BASE_URL=http://127.0.0.1:8000
   AI_STUB=true
   ```

   `BOT_API_KEY` в `.env` и тот, что читает бот, должны совпадать.
3. API должен быть запущен (см. выше), затем бот:

   ```bash
   backend/.venv/bin/python bot/main.py     # PowerShell: .\backend\.venv\Scripts\python.exe bot\main.py
   ```

   Бот опрашивает Telegram сам, туннель наружу не нужен. Если `TELEGRAM_BOT_TOKEN` пуст — бот сразу выйдет с этой ошибкой.
4. В Telegram: `/start` → пришлите текст вида `1 пара Матанализ лк, ауд. 214` (или фото расписания) → **Добавить**.
5. `/events` — список событий этого telegram-аккаунта; в веб этот список попадёт только после привязки аккаунтов (см. ограничение выше).

---

## Запуск мобильного приложения

Нужен Flutter SDK.

```bash
cd mobile
flutter create . --project-name calendai   # один раз: генерирует android/, ios/
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

На Android-эмуляторе localhost хост-машины — `http://10.0.2.2:8000`. Без запущенного API приложение работает офлайн на локальном SQLite.

---

## ИИ-парсер

`ai_module/` ходит в любой OpenAI-совместимый Vision API (OpenAI, DeepSeek, OpenRouter).

- Ключ и модель: `CALENDAI_API_KEY` + `CALENDAI_MODEL` + `CALENDAI_BASE_URL` (есть fallback на `OPENAI_*`).
- `AI_STUB=true` — работает заглушка: ключ не нужен, квота не списывается, возвращается тестовое занятие.
- `AI_STUB=false` — реальные вызовы, квота считается.

Квоты на неделю: `free` — 0, `plus` — 7, `pro` — 70 запросов. Сброс — раз в 7 дней (`week_reset_at`).

Проверка парсера из терминала:

```bash
backend/.venv/bin/python -m ai_module.cli --text "1 пара Матанализ лк, ауд. 214" --date 2026-09-08
backend/.venv/bin/python -m ai_module.cli --image schedule.png --date 2026-09-08 --tz +03:00
```

---

## API `/api/v1`

| Метод | Путь | Зачем |
|---|---|---|
| POST | `/auth/register` | email + пароль → JWT |
| POST | `/auth/login` | JWT |
| POST | `/auth/token` | OAuth2-форма для Swagger Authorize |
| POST | `/auth/telegram` | бот создаёт/находит пользователя (`X-Bot-Key`) |
| GET | `/auth/me` | профиль текущего пользователя |
| GET/POST | `/events` | список / создать |
| GET/PATCH/DELETE | `/events/{id}` | одно событие; DELETE — soft delete |
| POST | `/sync` | дифференциальный синк (`X-Device-Id` опционален) |
| POST | `/ai/parse-text` | текст → кандидаты |
| POST | `/ai/parse-image` | фото → кандидаты |
| POST | `/ai/confirm` | записать распознанное в календарь |

Парсер подключается из `ai_module/` через `backend/app/services/parser_bridge.py`.

---

## Клонировать только нужную часть кода

Репозиторий один, но скачивать всё не обязательно. Чтобы получить, например, только backend/web/bot без мобильного кода:

```bash
git clone --filter=blob:none --no-checkout git@github.com:Arturklik/CalendAI.git
cd CalendAI
git sparse-checkout init --cone
git sparse-checkout set backend web bot ai_module
git checkout <branch>
```

Наборы путей:

- backend-разработчик: `backend web bot ai_module`
- мобильный разработчик: `mobile ai_module backend/contracts`

Чтобы снова получить всё: `git sparse-checkout disable`. Это локальная настройка клона — на репозиторий и других участников не влияет.

---

## Что ещё не сделано

- привязка Telegram-аккаунта к email-аккаунту (календари пока раздельные);
- войс-ввод (Whisper);
- оплата планов;
- миграции схем (сейчас `create_all` + дроп устаревшей SQLite-схемы при старте);
- автоматические тесты backend.
