"""Общие FastAPI-зависимости: текущий пользователь по Bearer-токену."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..services import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось подтвердить учётные данные",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Извлекает пользователя из JWT access token."""
    try:
        user_id = auth_service.decode_token(
            token, expected_purpose=auth_service.PURPOSE_ACCESS
        )
    except auth_service.AuthError:
        raise _credentials_exception from None

    user = await db.get(User, user_id)
    if user is None:
        raise _credentials_exception
    return user
