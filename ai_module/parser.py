"""ScheduleParser — распознавание расписаний через OpenAI-совместимый Vision API.

Поддерживает DeepSeek, OpenRouter, GPT-4o-mini, Google Gemini и других OpenAI-совместимых
провайдеров. Результат — строго типизированный ScheduleParseResponse
(Pydantic v2), готовый к записи в календарь.

Конфигурация через аргументы конструктора или переменные окружения (.env):
    CALENDAI_API_KEY  (fallback OPENAI_API_KEY)   — API-ключ, обязателен;
    CALENDAI_BASE_URL (fallback OPENAI_BASE_URL)  — например https://generativelanguage.googleapis.com/v1beta/openai/;
    CALENDAI_MODEL    (fallback OPENAI_MODEL)     — по умолчанию gpt-4o-mini.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, NoReturn

from dotenv import load_dotenv
from openai import APIStatusError, BadRequestError, OpenAI

try:  # пакетный импорт (python -m ai_module.cli)
    from .models import ScheduleParseResponse
except ImportError:  # запуск скриптом из каталога ai_module
    from models import ScheduleParseResponse

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-1.5-flash"
DEFAULT_TIMEZONE_OFFSET = "+07:00"
_TZ_RE = re.compile(r"[+-](?:0\d|1[0-4]):[0-5]\d")
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_FALLBACK_STATUS_CODES = frozenset({404, 429, 503})
_MAX_PROVIDER_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_DELAY_SECONDS = 2.0
AI_CONFIGURATION_ERROR_MESSAGE = (
    "Ошибка конфигурации модели: проверьте CALENDAI_MODEL и API-ключ в .env"
)
logger = logging.getLogger(__name__)

# Академическая сетка звонков.
CLASS_PERIODS = (
    (1, "09:00", "10:35"),
    (2, "10:50", "12:25"),
    (3, "13:00", "14:35"),
    (4, "14:50", "16:25"),
    (5, "16:40", "18:15"),
)

_WEEKDAYS_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)

SYSTEM_PROMPT = """\
Ты — модуль распознавания университетских расписаний CalendAI.
Твоя задача — извлечь из расписания список занятий и вернуть результат
СТРОГО в формате JSON по заданной схеме, без markdown и пояснений.

Академическая сетка звонков (используй, если в расписании указан номер пары
без явного времени начала и конца):
1 пара: 09:00–10:35
2 пара: 10:50–12:25
3 пара: 13:00–14:35
4 пара: 14:50–16:25
5 пара: 16:40–18:15

Правила:
- Корневой JSON всегда является объектом с полем "events", содержащим массив занятий.
- Если время начала/конца занятия указано явно — используй его, а не сетку звонков.
- Часовой пояс задаёт пользователь. Все start_time и end_time формируй как
  ISO 8601 с часовым поясом, например "2026-09-08T09:00:00+07:00".
- Дату каждого занятия определяй по информации из самого расписания
  относительно опорной даты (дня отправки сообщения):
  * явная дата («21 сентября», «21.09», «2026-09-21») — используй её;
    если год не указан, бери год опорной даты;
  * день недели («Понедельник», «Пн», «СР») — возьми ближайшую дату с этим
    днём недели, начиная с опорной даты (если опорная дата — понедельник,
    а расписание на понедельник, то дата — сама опорная дата);
  * несколько дней недели в одном расписании (например, неделя Пн–Пт) —
    каждое занятие получает дату своего дня недели;
  * если в расписании нет ни дат, ни дней недели — используй опорную дату.
- event_type — строго одно из: "lecture", "practice", "lab", "exam", "other".
  Сокращения: лк/лекция → lecture; пр/пз/практика/семинар → practice;
  лаб/лр/лабораторная → lab; экз/экзамен/зачёт → exam; прочее → other.
- title — название дисциплины/события без пометок типа занятия.
- location — аудитория/корпус или ссылка; teacher — ФИО преподавателя.
  Если данных нет — null.
- description — дополнительные пометки (подгруппа, чётность недели и т.п.), иначе null.
- Ничего не выдумывай: распознавай только то, что реально есть в расписании.
"""


class AIProviderUnavailableError(RuntimeError):
    """AI provider remained unavailable after bounded transient-error retries."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"AI provider is temporarily unavailable (HTTP {status_code})")


class AIConfigurationError(RuntimeError):
    """Invalid AI model or credentials; retrying the same request will not help."""

    def __init__(self) -> None:
        super().__init__(AI_CONFIGURATION_ERROR_MESSAGE)


def _strict_json_schema() -> dict[str, Any]:
    """JSON Schema ScheduleParseResponse для OpenAI Structured Outputs.

    Strict-режим требует: additionalProperties=false, все поля в required,
    отсутствие default-значений (optional выражается через anyOf с null).
    """
    schema = ScheduleParseResponse.model_json_schema()

    def enforce(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for value in node.values():
                enforce(value)
        elif isinstance(node, list):
            for item in node:
                enforce(item)

    enforce(schema)
    return schema


class ScheduleParser:
    """Парсер расписаний (изображение или текст) -> ScheduleParseResponse."""

    # Плотные таблицы расписаний требуют высокой детализации изображения.
    IMAGE_DETAIL = "high"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 120.0,
        client: OpenAI | None = None,
        fallback_model: str | None = None,
    ) -> None:
        load_dotenv()
        self.api_key = (
            api_key or os.getenv("CALENDAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        if not self.api_key and client is None:
            raise ValueError(
                "API-ключ не задан: укажите CALENDAI_API_KEY/OPENAI_API_KEY "
                "в .env или передайте api_key в конструктор"
            )
        self.base_url = (
            base_url or os.getenv("CALENDAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        )
        self.model = (
            model
            or os.getenv("CALENDAI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or DEFAULT_MODEL
        )
        self.fallback_model = (
            fallback_model
            or os.getenv("CALENDAI_FALLBACK_MODEL")
            or self._default_fallback_model(self.model, self.base_url)
        )
        self._client = client or OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            # Retries are handled here so transient provider failures have a
            # bounded, deterministic backoff and a user-facing error type.
            max_retries=0,
        )

    # ---------------- Публичное API ----------------

    def parse_image(
        self,
        image_path: str | Path,
        base_date: datetime | date,
        timezone_offset: str = DEFAULT_TIMEZONE_OFFSET,
    ) -> ScheduleParseResponse:
        """Распознаёт расписание с изображения (скриншот/фото).

        `base_date` — опорная дата (день отправки сообщения): от неё
        вычисляются даты занятий, если в расписании указан день недели.
        """
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Изображение не найдено: {path}")
        mime = mimetypes.guess_type(path.name)[0]
        if not mime or not mime.startswith("image/"):
            raise ValueError(f"Файл не является изображением: {path}")
        self._validate_tz(timezone_offset)

        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        content: list[dict[str, Any]] = [
            {"type": "text", "text": self._user_prompt(base_date, timezone_offset)},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{image_b64}",
                    "detail": self.IMAGE_DETAIL,
                },
            },
        ]
        return self._complete(content)

    def parse_text(
        self,
        text: str,
        base_date: datetime | date,
        timezone_offset: str = DEFAULT_TIMEZONE_OFFSET,
    ) -> ScheduleParseResponse:
        """Распознаёт расписание из текста (например, пересланного сообщения).

        `base_date` — опорная дата (день отправки сообщения): от неё
        вычисляются даты занятий, если в расписании указан день недели.
        """
        if not text or not text.strip():
            raise ValueError("Пустой текст расписания")
        self._validate_tz(timezone_offset)

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    self._user_prompt(base_date, timezone_offset)
                    + "\n\nТекст расписания:\n"
                    + text.strip()
                ),
            }
        ]
        return self._complete(content)

    # ---------------- Внутреннее ----------------

    def _complete(self, user_content: list[dict[str, Any]]) -> ScheduleParseResponse:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        try:
            # Structured Outputs: строгая JSON Schema исключает галлюцинации формата.
            response = self._create_completion(
                model=self.model,
                messages=messages,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "schedule_parse_response",
                        "strict": True,
                        "schema": _strict_json_schema(),
                    },
                },
            )
        except BadRequestError as exc:
            # Fallback нужен только провайдерам, не поддерживающим response_format
            # json_schema. Не повторяем запрос в JSON-режиме при 503/429/ошибках сети.
            if not self._supports_json_schema_fallback(exc):
                raise
            response = self._create_completion(
                model=self.model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )

        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise RuntimeError(f"Модель отказалась отвечать: {refusal}")
        if not message.content:
            raise RuntimeError("Модель вернула пустой ответ")
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            return ScheduleParseResponse.model_validate_json(message.content)

        # Некоторые OpenAI-совместимые провайдеры игнорируют объектную JSON
        # Schema в fallback JSON-режиме и возвращают сам массив занятий.
        if isinstance(payload, list):
            payload = {"events": payload}
        return ScheduleParseResponse.model_validate(payload)

    def _create_completion(self, **request: Any) -> Any:
        """Request the primary model, then use the configured fallback when needed."""
        primary_model = str(request.get("model") or self.model)
        provider_error: APIStatusError | None = None
        for attempt in range(_MAX_PROVIDER_RETRIES + 1):
            try:
                return self._client.chat.completions.create(**request)
            except APIStatusError as exc:
                provider_error = exc
                self._log_provider_error(request, exc)
                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    break
                if attempt >= _MAX_PROVIDER_RETRIES:
                    break

                delay = min(
                    _RETRY_BASE_DELAY_SECONDS * (2**attempt),
                    _RETRY_MAX_DELAY_SECONDS,
                )
                time.sleep(delay)

        if provider_error is None:  # pragma: no cover - loop always returns or errors
            raise AssertionError("unreachable")

        if (
            provider_error.status_code in _FALLBACK_STATUS_CODES
            and self.fallback_model
            and self.fallback_model != primary_model
        ):
            logger.warning(
                "Primary AI model %s failed with HTTP %s; trying fallback model %s",
                primary_model,
                provider_error.status_code,
                self.fallback_model,
            )
            fallback_request = {**request, "model": self.fallback_model}
            try:
                return self._create_fallback_completion(fallback_request)
            except APIStatusError as fallback_error:
                if provider_error.status_code == 404:
                    raise AIConfigurationError() from provider_error
                self._raise_provider_error(fallback_error)

        self._raise_provider_error(provider_error)

    def _create_fallback_completion(self, request: dict[str, Any]) -> Any:
        """Retry temporary fallback failures, without recursively falling back."""
        for attempt in range(_MAX_PROVIDER_RETRIES + 1):
            try:
                return self._client.chat.completions.create(**request)
            except APIStatusError as exc:
                self._log_provider_error(request, exc)
                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    raise
                if attempt >= _MAX_PROVIDER_RETRIES:
                    raise

                delay = min(
                    _RETRY_BASE_DELAY_SECONDS * (2**attempt),
                    _RETRY_MAX_DELAY_SECONDS,
                )
                time.sleep(delay)

        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _default_fallback_model(model: str, base_url: str | None) -> str:
        """Choose a fallback from the same known provider when possible."""
        model_name = model.lower()
        provider_url = (base_url or "").lower()

        if "openrouter.ai" in provider_url:
            return "google/gemini-1.5-flash"
        if "deepseek" in provider_url or model_name.startswith("deepseek-"):
            return "deepseek-reasoner" if model_name == "deepseek-chat" else "deepseek-chat"
        if (
            "generativelanguage.googleapis.com" in provider_url
            or "gemini" in model_name
        ):
            return DEFAULT_GEMINI_FALLBACK_MODEL
        if "api.openai.com" in provider_url or model_name.startswith("gpt-"):
            return "gpt-4o" if model_name == "gpt-4o-mini" else "gpt-4o-mini"
        return DEFAULT_GEMINI_FALLBACK_MODEL

    @staticmethod
    def _log_provider_error(request: dict[str, Any], error: APIStatusError) -> None:
        """Log response details so provider configuration issues are diagnosable."""
        try:
            body = error.response.text
        except Exception:  # pragma: no cover - defensive for custom OpenAI clients
            body = ""
        body = body or str(getattr(error, "message", None) or error)
        logger.error(
            "AI provider request failed: model=%s status=%s response=%s",
            request.get("model"),
            error.status_code,
            body,
        )

    @staticmethod
    def _raise_provider_error(error: APIStatusError) -> NoReturn:
        if error.status_code in {401, 404}:
            raise AIConfigurationError() from error
        if error.status_code in _RETRYABLE_STATUS_CODES:
            raise AIProviderUnavailableError(error.status_code) from error
        raise error

    @staticmethod
    def _supports_json_schema_fallback(error: BadRequestError) -> bool:
        """Return true only for 400 responses that reject structured JSON mode."""
        message = str(error).lower()
        mentions_schema_mode = any(
            marker in message
            for marker in (
                "json_schema",
                "json schema",
                "response_format",
                "structured output",
                "structured outputs",
            )
        )
        explicitly_unsupported = any(
            marker in message
            for marker in (
                "not supported",
                "unsupported",
                "does not support",
                "only supports",
                "unknown parameter",
                "unknown name",
                "cannot find field",
                "unrecognized field",
                "unrecognized request argument",
            )
        )
        return mentions_schema_mode and explicitly_unsupported

    @staticmethod
    def _user_prompt(base_date: datetime | date, timezone_offset: str) -> str:
        weekday = _WEEKDAYS_RU[base_date.weekday()]
        return (
            f"Опорная дата (день отправки сообщения): {base_date:%Y-%m-%d} ({weekday}). "
            f"Часовой пояс: {timezone_offset}. "
            "Определи дату каждого занятия по самому расписанию: явная дата — "
            "используй её; день недели — ближайшая дата с этим днём недели, "
            "начиная с опорной; если ни дат, ни дней недели нет — опорная дата. "
            "Распознай все занятия."
        )

    @staticmethod
    def _validate_tz(timezone_offset: str) -> None:
        if not _TZ_RE.fullmatch(timezone_offset):
            raise ValueError(
                "Некорректное смещение часового пояса: "
                f"{timezone_offset!r} (ожидается ±HH:MM)"
            )
