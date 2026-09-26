"""AI-эндпоинты: /api/v1/ai/parse-image, /api/v1/ai/parse-text
и /api/v1/ai/parse-voice.

Тонкий HTTP-слой над `app/services/ai_service.py` (адаптер ScheduleParser
из ai_module). Требуют авторизации и настроенного CALENDAI_API_KEY.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from ai_module import ScheduleParseResponse

from ..models.user import User
from ..services import ai_service
from .deps import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 МБ
MAX_AUDIO_SIZE_BYTES = 20 * 1024 * 1024  # 20 МБ
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm"}


class ParseTextRequest(BaseModel):
    """Запрос на распознавание расписания из текста."""

    text: str = Field(min_length=1, max_length=20_000)
    # Опорная дата (день отправки сообщения): от неё вычисляются даты
    # занятий, если в расписании указан день недели, а не дата.
    base_date: date
    timezone_offset: str = "+07:00"


def _map_ai_errors(exc: Exception) -> HTTPException:
    """Единообразное преобразование ошибок AI-слоя в HTTP."""
    if isinstance(exc, ai_service.AIServiceUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    if isinstance(exc, ai_service.UnsupportedImageError):
        return HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=422, detail=str(exc)
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Ошибка распознавания: {exc}",
    )


@router.post("/parse-image", response_model=ScheduleParseResponse)
async def parse_image(
    file: UploadFile = File(..., description="Скриншот/фото расписания"),
    base_date: date = Query(
        ...,
        description="Опорная дата — день отправки сообщения (YYYY-MM-DD)",
    ),
    tz: str = Query(default="+07:00", description="Часовой пояс ±HH:MM"),
    current_user: User = Depends(get_current_user),
) -> ScheduleParseResponse:
    """Распознаёт расписание с изображения через Vision API."""
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=422,
            detail="Пустой файл",
        )
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой (максимум 20 МБ)",
        )
    try:
        return await ai_service.parse_schedule_image(
            image_bytes, file.content_type, base_date, tz
        )
    except Exception as exc:
        raise _map_ai_errors(exc) from exc


@router.post("/parse-text", response_model=ScheduleParseResponse)
async def parse_text(
    request: ParseTextRequest,
    current_user: User = Depends(get_current_user),
) -> ScheduleParseResponse:
    """Распознаёт расписание из текста (пересланное сообщение и т.п.)."""
    try:
        return await ai_service.parse_schedule_text(
            request.text, request.base_date, request.timezone_offset
        )
    except Exception as exc:
        raise _map_ai_errors(exc) from exc


@router.post("/parse-voice", response_model=ScheduleParseResponse)
async def parse_voice(
    file: UploadFile = File(..., description="Голосовое сообщение/аудиозапись"),
    base_date: date = Query(
        ...,
        description="Опорная дата — день отправки сообщения (YYYY-MM-DD)",
    ),
    tz: str = Query(default="+07:00", description="Часовой пояс ±HH:MM"),
    current_user: User = Depends(get_current_user),
) -> ScheduleParseResponse:
    """Транскрибирует аудио и распознаёт расписание из полученного текста."""
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются файлы .mp3, .wav, .ogg, .m4a и .webm",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Пустой файл")
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой (максимум 20 МБ)",
        )

    try:
        text = await ai_service.transcribe_audio(audio_bytes, filename)
        return await ai_service.parse_schedule_text(text, base_date, tz)
    except Exception as exc:
        raise _map_ai_errors(exc) from exc
