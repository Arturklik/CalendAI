"""Схемы аутентификации и пользователя."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Регистрация нового пользователя."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Вход по email и паролю."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Token(BaseModel):
    """JWT access token (Bearer)."""

    access_token: str
    token_type: str = "bearer"


class TelegramLinkToken(BaseModel):
    """Одноразовый токен для привязки Telegram-аккаунта через /start."""

    link_token: str
    expires_in_seconds: int


class UserResponse(BaseModel):
    """Публичное представление пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    telegram_id: int | None
    subscription_tier: str
    created_at: datetime
