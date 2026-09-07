# CalendAI

Экосистема расписания: фото/текст → ИИ → календарь. Закрытая бета без оплаты.

| Часть | Кто | Где |
|---|---|---|
| Backend API, БД, синк, Telegram-бот | Антон | `backend/`, `bot/`, `web/` |
| Flutter (офлайн-календарь) + AI-парсер | Артур | `mobile/`, `ai_module/` |

Канонический контракт события — в `mobile/AGENTS.md` и `backend/contracts/`.

---

## Как задумано

Пользователь на ходу кидает в **Telegram** фото расписания или текст. Бот показывает распознанные пары и спрашивает подтверждение. После «Добавить» события попадают в общую базу. Телефон и сайт потом забирают их синком.

Веб и мобилка — смотреть и править руками. Telegram — быстрый ввод.

## Как сделано сейчас

Бот уже ходит в наш API, не в пустоту.

1. API должен быть запущен на `http://127.0.0.1:8000`.
2. В Telegram пишешь боту `/start`.
3. Бот создаёт пользователя по `telegram_id` (это **отдельный** аккаунт, не email с сайта).
4. Кидаешь **фото** или **текст** → ИИ (пока заглушка, если нет ключа) → превью.
5. Кнопки **Добавить** / **Отмена**. Добавить пишет события в БД.
6. `/events` — список ближайших событий этого telegram-аккаунта.

Ещё нет:

- привязки бота к email с телефона (календари пока разные);
- войса (Whisper);
- оплаты.

Локально бот работает так: процесс на твоём ПК сам опрашивает Telegram и сам стучится в `localhost`. Туннель наружу не нужен.

---

## Запуск из VS Code / Cursor

Нужен Python 3.12. Виртуальное окружение уже лежит в `backend/.venv`.

1. Открой папку `CalendAI` как корень воркспейса.
2. Расширения: **Python** и **Python Debugger** (`ms-python.python`, `ms-python.debugpy`).
3. Interpreter: `backend/.venv/Scripts/python.exe` (в `.vscode/settings.json` уже прописан).
4. Скопируй `backend/.env.example` → `backend/.env`, если файла ещё нет.
5. Для SQLite на локалке в `.env` должно быть:
   ```
   DATABASE_URL=sqlite:///./calendai.db
   ```
6. Run and Debug (`Ctrl+Shift+D`):
   - **CalendAI API** — сайт + REST API;
   - **CalendAI Telegram bot** — только бот (API уже должен работать);
   - **CalendAI: API + bot** — оба сразу.

После старта API:

- веб-календарь: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- health: http://127.0.0.1:8000/health

### Telegram с локалки

1. В Telegram: [@BotFather](https://t.me/BotFather) → `/newbot` → скопируй токен.
2. В `backend/.env`:
   ```
   TELEGRAM_BOT_TOKEN=123:AA...
   BOT_API_KEY=dev-bot-key-change-me
   API_BASE_URL=http://127.0.0.1:8000
   AI_STUB=true
   ```
   `BOT_API_KEY` в `.env` и то, что читает бот, должны совпадать.
3. Запусти **CalendAI: API + bot**.
4. Найди своего бота в Telegram → `/start` → кинь текст вроде `1 пара Матанализ лк, ауд. 214` → **Добавить**.
5. `/events` или веб: события этого telegram-пользователя. В веб нужно войти **тем же** аккаунтом — пока это не так, смотри список через `/events` в боте.

Если токен пустой, бот сразу выходит с ошибкой `TELEGRAM_BOT_TOKEN is empty`.

### Терминал VS Code (если без F5)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Второе окно:

```powershell
cd D:\WorkSpace\project\CalendAI
.\backend\.venv\Scripts\python.exe bot\main.py
```

---

## Backend (Антон)

Стек: FastAPI, SQLAlchemy, JWT, SQLite (локально) / PostgreSQL (цель).

### API `/api/v1`

| Метод | Путь | Зачем |
|---|---|---|
| POST | `/auth/register` | email + пароль |
| POST | `/auth/login` | JWT |
| GET | `/auth/me` | профиль |
| POST | `/auth/telegram` | бот создаёт/находит пользователя (`X-Bot-Key`) |
| GET/POST | `/events` | список / создать |
| GET/PATCH/DELETE | `/events/{id}` | одно событие, DELETE = soft delete |
| POST | `/sync` | дифференциальный синк с мобилки |
| POST | `/ai/parse-text` | текст → кандидаты |
| POST | `/ai/parse-image` | фото → кандидаты |
| POST | `/ai/confirm` | записать распознанное в календарь |

Синк: тело `{ "last_sync_timestamp": null \| ISO, "client_changes": [CalendarEvent] }`. Ответ `{ "sync_timestamp", "server_changes" }`. Клиент побеждает, только если `client.updated_at > server.updated_at`.

### Переменные `.env`

См. `backend/.env.example`. Главные:

- `DATABASE_URL` — sqlite или postgres
- `SECRET_KEY` — подпись JWT
- `TELEGRAM_BOT_TOKEN` — от BotFather
- `BOT_API_KEY` — секрет между ботом и API
- `CALENDAI_API_KEY` / `CALENDAI_BASE_URL` / `CALENDAI_MODEL` — Vision (DeepSeek / OpenAI)
- `AI_STUB=true` — без ключа не вызывать платную модель

Парсер Артура подключается из `ai_module/` (`ScheduleParser.parse_image` / `parse_text`).

---

## Мобилка (Артур)

`mobile/` — Flutter, локальный SQLite, кнопка синка уже бьёт в `POST /api/v1/sync`. Нужен Flutter SDK:

```powershell
cd mobile
flutter create . --project-name calendai
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

На Android-эмуляторе хост машины: `http://10.0.2.2:8000`.

---

## Postgres (когда понадобится не только локальный файл)

```powershell
cd backend
docker compose up -d
```

В `.env` раскомментируй postgres `DATABASE_URL` из `.env.example`.
