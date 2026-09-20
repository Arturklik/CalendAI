# Project CalendAI — Instructions & Standards

## Overview
CalendAI is an offline-first schedule and calendar ecosystem. It automatically converts timetable images, screenshots, and audio messages into calendar events via external AI APIs (DeepSeek / Vision API / Whisper), with local SQLite caching and manual editing capabilities.

## Architecture & Responsibilities
- Framework: Flutter (Android & iOS).
- Local Database: SQLite (via Drift or sqflite) with full offline-first functionality.
- Sync Strategy: Differential sync via `SyncRepository`; рабочая реализация — `HttpSyncRepository` (`lib/repositories/http_sync_repository.dart`) поверх `POST /api/v1/sync` (Last-Write-Wins, см. `backend/app/services/sync_service.py`). JWT хранится в `AuthStorage` (SharedPreferences), base URL — `ApiConfig` (Android-эмулятор `10.0.2.2`, iOS/desktop `127.0.0.1`, кастомный IP через `ApiConfig.setCustomHost`). `MockSyncRepository` — только для UI-разработки без бэкенда.
- AI Module: Python service using Pydantic v2 and external APIs (OpenAI SDK / DeepSeek / Vision models) with strict JSON output.
- Backend (`backend/`): FastAPI (async) + PostgreSQL (SQLAlchemy 2.0 asyncio + asyncpg) + Alembic, JWT-аутентификация, Telegram-бот (aiogram 3). Зеркалирует канонический контракт события; тесты на pytest (SQLite in-memory), запуск: `cd backend && pytest -q`; инфраструктура: `docker compose -f backend/docker-compose.yml up --build` из корня репозитория.

## Canonical Data Contract (Event Schema)
Every calendar event MUST strictly match this specification:
- `id`: String (UUIDv4)
- `title`: String (subject or event title)
- `event_type`: String ("lecture" | "practice" | "lab" | "exam" | "other")
- `start_time`: String (ISO 8601 with timezone, e.g. "2026-09-08T09:00:00+07:00")
- `end_time`: String (ISO 8601 with timezone, e.g. "2026-09-08T10:35:00+07:00")
- `location`: String? (auditorium/room or link)
- `teacher`: String? (lecturer's name)
- `description`: String? (additional notes)
- `recurrence_rule`: String? (RFC 5545 RRULE, e.g. "FREQ=WEEKLY;INTERVAL=2")
- `updated_at`: String (ISO 8601 UTC timestamp)
- `is_deleted`: Boolean (Soft delete flag)

## Coding Standards
1. Offline-First: The mobile app must operate without internet access.
2. No premature coupling: Network sync must be hidden behind an interface.
3. Defensive typing: Always handle nullable fields safely.
4. Keep implementations minimal, structured, and free of unused dependencies.
