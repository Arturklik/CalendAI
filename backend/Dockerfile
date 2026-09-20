# CalendAI backend: FastAPI + Telegram-бот + ai_module.
# Сборка ведётся из КОРНЯ монорепозитория:
#   docker build -f backend/Dockerfile -t calendai-backend .

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Зависимости: backend/requirements.txt включает и зависимости
# ai_module (openai, pydantic, python-dotenv).
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Исходники. PYTHONPATH=/app делает импортируемыми оба пакета:
# `app` (backend/app) и `ai_module` (ai_module).
COPY ai_module /app/ai_module
COPY backend /app/backend

ENV PYTHONPATH=/app
WORKDIR /app/backend

EXPOSE 8000

# Миграции применяются при старте контейнера, затем поднимается API
# (Telegram-бот стартует в том же процессе через lifespan).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
