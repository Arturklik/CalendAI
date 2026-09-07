"""ScheduleParser — распознавание расписаний через OpenAI-совместимый Vision API.

Поддерживает DeepSeek, OpenRouter, GPT-4o-mini и других OpenAI-совместимых
провайдеров. Результат — строго типизированный ScheduleParseResponse
(Pydantic v2), готовый к записи в календарь.

Конфигурация через аргументы конструктора или переменные окружения (.env):
    CALENDAI_API_KEY  (fallback OPENAI_API_KEY)   — API-ключ, обязателен;
    CALENDAI_BASE_URL (fallback OPENAI_BASE_URL)  — например https://api.deepseek.com;
    CALENDAI_MODEL    (fallback OPENAI_MODEL)     — по умолчанию gpt-4o-mini.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional, Union

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

try:  # пакетный импорт (python -m ai_module.cli)
    from .models import ScheduleParseResponse
except ImportError:  # запуск скриптом из каталога ai_module
    from models import ScheduleParseResponse

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEZONE_OFFSET = "+07:00"
_TZ_RE = re.compile(r"[+-](?:0\d|1[0-4]):[0-5]\d")

# Академическая сетка звонков.
CLASS_PERIODS = (
    (1, "09:00", "10:35"),
    (2, "10:50", "12:25"),
    (3, "13:00", "14:35"),
    (4, "14:50", "16:25"),
    (5, "16:40", "18:15"),
)

_WEEKDAYS_RU = (
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
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
- Если время начала/конца занятия указано явно — используй его, а не сетку звонков.
- Дату занятий и часовой пояс задаёт пользователь. Все start_time и end_time
  формируй как ISO 8601 с часовым поясом, например "2026-09-08T09:00:00+07:00".
- event_type — строго одно из: "lecture", "practice", "lab", "exam", "other".
  Сокращения: лк/лекция → lecture; пр/пз/практика/семинар → practice;
  лаб/лр/лабораторная → lab; экз/экзамен/зачёт → exam; прочее → other.
- title — название дисциплины/события без пометок типа занятия.
- location — аудитория/корпус или ссылка; teacher — ФИО преподавателя.
  Если данных нет — null.
- description — дополнительные пометки (подгруппа, чётность недели и т.п.), иначе null.
- Ничего не выдумывай: распознавай только то, что реально есть в расписании.
"""


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
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        *,
        timeout: float = 120.0,
        client: Optional[OpenAI] = None,
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
            model or os.getenv("CALENDAI_MODEL") or os.getenv("OPENAI_MODEL")
            or DEFAULT_MODEL
        )
        self._client = client or OpenAI(
            api_key=self.api_key, base_url=self.base_url, timeout=timeout
        )

    # ---------------- Публичное API ----------------

    def parse_image(
        self,
        image_path: Union[str, Path],
        target_date: Union[datetime, date],
        timezone_offset: str = DEFAULT_TIMEZONE_OFFSET,
    ) -> ScheduleParseResponse:
        """Распознаёт расписание с изображения (скриншот/фото)."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Изображение не найдено: {path}")
        mime = mimetypes.guess_type(path.name)[0]
        if not mime or not mime.startswith("image/"):
            raise ValueError(f"Файл не является изображением: {path}")
        self._validate_tz(timezone_offset)

        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        content: list[dict[str, Any]] = [
            {"type": "text", "text": self._user_prompt(target_date, timezone_offset)},
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
        target_date: Union[datetime, date],
        timezone_offset: str = DEFAULT_TIMEZONE_OFFSET,
    ) -> ScheduleParseResponse:
        """Распознаёт расписание из текста (например, пересланного сообщения)."""
        if not text or not text.strip():
            raise ValueError("Пустой текст расписания")
        self._validate_tz(timezone_offset)

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    self._user_prompt(target_date, timezone_offset)
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
            response = self._client.chat.completions.create(
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
        except BadRequestError:
            # Часть провайдеров (например, DeepSeek) не поддерживает json_schema —
            # откатываемся на базовый JSON-режим (структуру задаёт промпт).
            response = self._client.chat.completions.create(
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
        return ScheduleParseResponse.model_validate_json(message.content)

    @staticmethod
    def _user_prompt(
        target_date: Union[datetime, date], timezone_offset: str
    ) -> str:
        weekday = _WEEKDAYS_RU[target_date.weekday()]
        return (
            f"Дата занятий: {target_date:%Y-%m-%d} ({weekday}). "
            f"Часовой пояс: {timezone_offset}. "
            "Распознай все занятия этого дня."
        )

    @staticmethod
    def _validate_tz(timezone_offset: str) -> None:
        if not _TZ_RE.fullmatch(timezone_offset):
            raise ValueError(
                "Некорректное смещение часового пояса: "
                f"{timezone_offset!r} (ожидается ±HH:MM)"
            )
