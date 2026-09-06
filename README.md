# CalendAI

Офлайн-первый календарь расписания: конвертирует фото и скриншоты расписания
(а также текстовые сообщения) в события календаря через внешние AI API
(DeepSeek / Vision API / Whisper), хранит всё локально в SQLite и позволяет
редактировать события вручную.

Репозиторий состоит из двух частей:

| Часть | Стек | Назначение |
|---|---|---|
| **Мобильный клиент** (`lib/`) | Flutter (Android / iOS), SQLite (sqflite) | Офлайн-календарь, локальное хранилище, синхронизация |
| **AI-модуль** (`ai_module/`) | Python 3.10+, Pydantic v2, OpenAI SDK | Распознавание расписаний через OpenAI-совместимый Vision API |

## Мобильный клиент

- Полностью офлайн-первый: приложение работает без интернета.
- Дифференциальная синхронизация за интерфейсом `SyncRepository`
  (пока используется `MockSyncRepository`, до готовности backend API).
- Локальное хранилище SQLite: таблица `events`, диапазонные запросы,
  upsert, мягкое удаление (soft delete).
- Экран календаря: месячная сетка, список занятий на день, цветовая
  дифференциация типов (лекция — синий, лабораторная — оранжевый,
  практика — зелёный), ручное создание событий.

### Структура

```
lib/
├── main.dart                       # точка входа
├── models/event.dart               # Event + EventType (канонический контракт)
├── database/app_database.dart      # SQLite-слой (синглтон)
├── repositories/
│   ├── sync_repository.dart        # интерфейс синхронизации
│   └── mock_sync_repository.dart   # мок до готовности backend
└── screens/calendar_screen.dart    # экран календаря
```

### Запуск

```bash
flutter pub get
flutter create --platforms=android,ios .   # однократно: сгенерировать платформенные папки
flutter run
```

Проверки:

```bash
flutter analyze
flutter test
```

## AI-модуль

Сервис `ScheduleParser` принимает изображение расписания или текст, отправляет
запрос в OpenAI-совместимый Vision API и возвращает строго структурированный
список событий (Pydantic v2, Structured Outputs с JSON Schema), готовых
к записи в календарь.

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

python cli.py --image schedule.png --date 2026-09-08
python cli.py --text "1 пара Матанализ лк, ауд. 214" --date 2026-09-08
python cli.py --image schedule.png --date 2026-09-08 --tz +03:00
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
