"""Эндпоинты аутентификации: /api/v1/auth/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models.user import User
from ..schemas.auth import (
    TelegramLinkToken,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from ..services import auth_service
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Регистрация нового пользователя."""
    user = await auth_service.register_user(db, data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )
    return user


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    """Вход: выдача JWT access token."""
    user = await auth_service.authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=auth_service.create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Профиль текущего пользователя."""
    return current_user


@router.post("/telegram-link-token", response_model=TelegramLinkToken)
async def telegram_link_token(
    current_user: User = Depends(get_current_user),
) -> TelegramLinkToken:
    """Одноразовый токен для команды бота `/start <link_token>`."""
    settings = get_settings()
    return TelegramLinkToken(
        link_token=auth_service.create_telegram_link_token(current_user.id),
        expires_in_seconds=settings.telegram_link_token_expire_minutes * 60,
    )
