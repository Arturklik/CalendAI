from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CalendAI"
    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./calendai.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    algorithm: str = "HS256"

    bot_api_key: str = "dev-bot-key-change-me"
    telegram_bot_token: str = ""
    api_base_url: str = "http://127.0.0.1:8000"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    vision_model: str = "gpt-4o-mini"
    calendai_api_key: str = ""
    calendai_base_url: str = ""
    calendai_model: str = ""
    ai_stub: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
