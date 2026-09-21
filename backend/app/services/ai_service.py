"""Адаптер к существующему AI-модулю распознавания расписаний.

Использует `ai_module.parser.ScheduleParser` из корня монорепозитория
(путь настраивается в `app/__init__.py`). Синхронные вызовы OpenAI SDK
выполняются в thread pool, чтобы не блокировать event loop FastAPI.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import date
from pathlib import Path

from ai_module import ScheduleParser, ScheduleParseResponse

from ..config import get_settings

# Допустимые MIME -> расширение временного файла для ScheduleParser.
_IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class AIServiceUnavailableError(Exception):
    """AI-модуль не сконфигурирован (нет API-ключа)."""


class UnsupportedImageError(Exception):
    """Неподдерживаемый тип изображения."""


_parser: ScheduleParser | None = None


def get_parser() -> ScheduleParser:
    """Ленивая инициализация ScheduleParser (один экземпляр на процесс)."""
    global _parser
    if _parser is None:
        settings = get_settings()
        if not settings.ai_available:
            raise AIServiceUnavailableError(
                "AI-модуль не сконфигурирован: задайте CALENDAI_API_KEY в .env"
            )
        _parser = ScheduleParser(
            api_key=settings.calendai_api_key,
            base_url=settings.calendai_base_url,
            model=settings.calendai_model,
        )
    return _parser


def reset_parser() -> None:
    """Сброс кэшированного парсера (для тестов)."""
    global _parser
    _parser = None


async def parse_schedule_image(
    image_bytes: bytes,
    content_type: str | None,
    base_date: date,
    timezone_offset: str,
) -> ScheduleParseResponse:
    """Распознаёт расписание с изображения (скриншот/фото).

    `base_date` — опорная дата (день отправки сообщения) в таймзоне
    пользователя: от неё вычисляются даты занятий по дню недели.

    ScheduleParser работает с путём к файлу, поэтому содержимое
    сохраняется во временный файл и удаляется после вызова.
    """
    suffix = _IMAGE_SUFFIXES.get(content_type or "", ".jpg")
    if content_type is not None and content_type not in _IMAGE_SUFFIXES:
        raise UnsupportedImageError(
            f"Неподдерживаемый тип изображения: {content_type}"
        )

    parser = get_parser()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False
        ) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)
        return await asyncio.to_thread(
            parser.parse_image, tmp_path, base_date, timezone_offset
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


async def parse_schedule_text(
    text: str,
    base_date: date,
    timezone_offset: str,
) -> ScheduleParseResponse:
    """Распознаёт расписание из текста (пересланное сообщение и т.п.).

    `base_date` — опорная дата (день отправки сообщения) в таймзоне
    пользователя: от неё вычисляются даты занятий по дню недели.
    """
    parser = get_parser()
    return await asyncio.to_thread(
        parser.parse_text, text, base_date, timezone_offset
    )


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Транскрибация аудио (голосовые сообщения Telegram) через Whisper.

    Использует тот же OpenAI-совместимый клиент, что и ScheduleParser.
    Требует провайдера с поддержкой Whisper API (например, OpenAI).
    """
    parser = get_parser()  # проверяет доступность AI-конфигурации
    client = parser._client  # noqa: SLF001 — единый клиент провайдера
    model = get_settings().whisper_model

    def _transcribe() -> str:
        result = client.audio.transcriptions.create(
            model=model,
            file=(filename, audio_bytes),
        )
        return result.text

    text = await asyncio.to_thread(_transcribe)
    if not text or not text.strip():
        raise ValueError("Не удалось распознать речь в аудиосообщении")
    return text
