"""Тесты промптов ScheduleParser: опорная дата и вывод даты по дню недели.

Клиент OpenAI подменяется заглушкой, сеть не используется.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ai_module import ScheduleParser
from ai_module.parser import SYSTEM_PROMPT


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.refusal: str | None = None


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse('{"events": []}')


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    """Минимальная заглушка OpenAI-клиента (без сети)."""

    def __init__(self) -> None:
        self.chat = _FakeChat()


def _user_text(client: _FakeClient) -> str:
    messages = client.chat.completions.calls[0]["messages"]
    return messages[1]["content"][0]["text"]


def test_system_prompt_requires_weekday_resolution() -> None:
    assert "день недели" in SYSTEM_PROMPT
    assert "ближайшую дату" in SYSTEM_PROMPT
    assert "опорной даты" in SYSTEM_PROMPT
    assert "опорную дату" in SYSTEM_PROMPT


def test_user_prompt_contains_base_date_and_timezone() -> None:
    prompt = ScheduleParser._user_prompt(date(2026, 9, 20), "+07:00")
    assert "Опорная дата" in prompt
    assert "2026-09-20" in prompt
    assert "воскресенье" in prompt
    assert "+07:00" in prompt
    assert "день недели" in prompt
    # Прежняя жёсткая формулировка «Дата занятий» больше не используется.
    assert "Дата занятий" not in prompt


def test_parse_text_sends_base_date_in_user_message() -> None:
    client = _FakeClient()
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    parser.parse_text(
        "Понедельник: Математический анализ, 1 пара, ауд. 214",
        date(2026, 9, 20),
        "+07:00",
    )

    messages = client.chat.completions.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    user_text = _user_text(client)
    assert "2026-09-20" in user_text
    assert "воскресенье" in user_text
    assert "Текст расписания:" in user_text
    assert "Математический анализ" in user_text


def test_parse_text_rejects_invalid_timezone() -> None:
    client = _FakeClient()
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    try:
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20), "МСК")
    except ValueError as exc:
        assert "часового пояса" in str(exc)
    else:  # pragma: no cover - защита от регрессии
        raise AssertionError("Ожидалась ValueError для некорректной таймзоны")
