from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    TelegramUpsert,
    TokenResponse,
    UserLogin,
    UserPublic,
    UserRegister,
)
from app.security import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        timezone=payload.timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login_json(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email.lower(), payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password form compatibility for Swagger Authorize."""
    user = authenticate_user(db, username.lower(), password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/telegram", response_model=TokenResponse)
def upsert_telegram_user(
    payload: TelegramUpsert,
    db: Session = Depends(get_db),
    x_bot_key: str | None = Header(default=None),
) -> TokenResponse:
    """Create or fetch a user by Telegram id. Called by the bot with X-Bot-Key."""
    if not settings.bot_api_key or x_bot_key != settings.bot_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot key")

    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if user is None:
        user = User(
            telegram_id=payload.telegram_id,
            display_name=payload.display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif payload.display_name and user.display_name != payload.display_name:
        user.display_name = payload.display_name
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)
