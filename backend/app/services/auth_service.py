"""Аутентификация: хеширование паролей (bcrypt), выпуск и проверка JWT."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.user import User
from ..schemas.auth import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Назначение токенов — чтобы токен привязки Telegram нельзя было
# использовать как access token и наоборот.
PURPOSE_ACCESS = "access"
PURPOSE_TG_LINK = "tg_link"


class AuthError(Exception):
    """Ошибка аутентификации/авторизации (невалидный токен, логин и т.п.)."""


# ---------------- Пароли ----------------


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


# ---------------- JWT ----------------


def _create_token(subject: uuid.UUID, purpose: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "purpose": purpose,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        user_id,
        PURPOSE_ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_telegram_link_token(user_id: uuid.UUID) -> str:
    """Короткоживущий токен для команды бота `/start <link_token>`."""
    settings = get_settings()
    return _create_token(
        user_id,
        PURPOSE_TG_LINK,
        timedelta(minutes=settings.telegram_link_token_expire_minutes),
    )


def decode_token(token: str, *, expected_purpose: str) -> uuid.UUID:
    """Валидация JWT. Возвращает user_id или бросает AuthError."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("purpose") != expected_purpose:
            raise AuthError("Недопустимое назначение токена")
        subject = payload.get("sub")
        if not subject:
            raise AuthError("В токене отсутствует sub")
        return uuid.UUID(subject)
    except (JWTError, ValueError) as exc:
        raise AuthError("Невалидный или просроченный токен") from exc


# ---------------- Пользователи ----------------


async def register_user(db: AsyncSession, data: UserCreate) -> User | None:
    """Создаёт пользователя. Возвращает None, если email уже занят."""
    email = data.email.lower()
    existing = await db.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        return None
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    """Проверка логина/пароля. Возвращает User или None."""
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> bool:
    """Проверяет текущий пароль и сохраняет новый хеш."""
    if not verify_password(current_password, user.password_hash):
        return False

    user.password_hash = hash_password(new_password)
    await db.commit()
    return True
