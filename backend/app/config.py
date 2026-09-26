"""Конфигурация приложения (Pydantic Settings).

Все параметры читаются из переменных окружения / корневого файла `.env`
(см. корневой `.env.example`). Префиксы не используются — имена переменных
совпадают с именами полей в UPPER_CASE.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки backend-сервиса CalendAI."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Общее ---
    app_name: str = "CalendAI Backend"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- База данных ---
    # Асинхронный драйвер asyncpg, например:
    # postgresql+asyncpg://calendai:calendai@localhost:5432/calendai
    database_url: str = "postgresql+asyncpg://calendai:calendai@localhost:5432/calendai"

    # --- JWT ---
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 дней
    telegram_link_token_expire_minutes: int = 15

    # --- AI (OpenAI-совместимый провайдер, см. ai_module) ---
    calendai_api_key: str | None = None
    calendai_base_url: str | None = None
    calendai_model: str | None = None
    calendai_fallback_model: str | None = None

    # --- Telegram-бот ---
    telegram_bot_token: str | None = None
    bot_default_timezone: str = "+07:00"
    whisper_model: str = "whisper-1"
    bot_mode: Literal["polling", "webhook"] = "polling"
    # Публичный HTTPS-URL сервиса для webhook, например https://api.example.com
    webhook_url: str | None = None
    webhook_path: str = "/tg/webhook"
    webhook_secret: str | None = None

    @property
    def ai_available(self) -> bool:
        """AI-эндпоинты активны только при наличии API-ключа."""
        return bool(self.calendai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Кэшированный доступ к настройкам (dependency для FastAPI)."""
    return Settings()
