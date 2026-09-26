"""Тесты промптов ScheduleParser: опорная дата и вывод даты по дню недели.

Клиент OpenAI подменяется заглушкой, сеть не используется.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest
from app.api.ai import _map_ai_errors
from openai import APIStatusError, BadRequestError

from ai_module import ScheduleParser
from ai_module import parser as parser_module
from ai_module.parser import (
    SYSTEM_PROMPT,
    AIConfigurationError,
    AIProviderUnavailableError,
)


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
    def __init__(
        self,
        content: str = '{"events": []}',
        outcomes: list[Any] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.content = content
        self.outcomes = list(outcomes or [])

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(
        self,
        content: str = '{"events": []}',
        outcomes: list[Any] | None = None,
    ) -> None:
        self.completions = _FakeCompletions(content, outcomes)


class _FakeClient:
    """Минимальная заглушка OpenAI-клиента (без сети)."""

    def __init__(
        self,
        content: str = '{"events": []}',
        outcomes: list[Any] | None = None,
    ) -> None:
        self.chat = _FakeChat(content, outcomes)


def _status_error(
    status_code: int,
    message: str,
    *,
    error_type: type[APIStatusError] = APIStatusError,
) -> APIStatusError:
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx.Response(status_code, content=message.encode(), request=request)
    return error_type(message, response=response, body={"error": message})


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


def test_parse_text_accepts_bare_event_array_from_provider() -> None:
    client = _FakeClient(
        '[{"title":"Основы анализа","event_type":"lecture",'
        '"start_time":"2026-09-28T09:00:00+07:00",'
        '"end_time":"2026-09-28T10:35:00+07:00",'
        '"location":null,"teacher":null,"description":null}]'
    )
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    response = parser.parse_text("Понедельник: Основы анализа", date(2026, 9, 28))

    assert len(response.events) == 1
    assert response.events[0].title == "Основы анализа"


def test_parse_text_rejects_invalid_timezone() -> None:
    client = _FakeClient()
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    try:
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20), "МСК")
    except ValueError as exc:
        assert "часового пояса" in str(exc)
    else:  # pragma: no cover - защита от регрессии
        raise AssertionError("Ожидалась ValueError для некорректной таймзоны")


def test_parse_text_retries_transient_503_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(parser_module.time, "sleep", sleeps.append)
    client = _FakeClient(
        outcomes=[
            _status_error(503, "model is overloaded"),
            _status_error(503, "model is overloaded"),
            _FakeResponse('{"events": []}'),
        ]
    )
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    result = parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert result.events == []
    assert len(client.chat.completions.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_parse_text_raises_friendly_provider_error_after_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(parser_module.time, "sleep", sleeps.append)
    client = _FakeClient(
        outcomes=[_status_error(503, "high demand") for _ in range(8)]
    )
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    with pytest.raises(AIProviderUnavailableError) as raised:
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert raised.value.status_code == 503
    assert len(client.chat.completions.calls) == 8
    assert sleeps == [0.5, 1.0, 2.0, 0.5, 1.0, 2.0]


@pytest.mark.parametrize("status_code", [404, 429, 503])
def test_provider_errors_use_fallback_model_and_log_response_body(
    status_code: int,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(parser_module.time, "sleep", sleeps.append)
    primary_failures = 1 if status_code == 404 else 4
    client = _FakeClient(
        outcomes=[
            _status_error(status_code, "provider quota exhausted")
            for _ in range(primary_failures)
        ]
        + [_FakeResponse('{"events": []}')]
    )
    parser = ScheduleParser(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,  # type: ignore[arg-type]
    )

    with caplog.at_level("ERROR", logger=parser_module.__name__):
        response = parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert response.events == []
    models = [call["model"] for call in client.chat.completions.calls]
    assert models == ["gemini-2.0-flash"] * primary_failures + ["gemini-1.5-flash"]
    assert "provider quota exhausted" in caplog.text
    assert len(sleeps) == (3 if status_code in {429, 503} else 0)


def test_401_is_reported_as_configuration_error_without_model_fallback() -> None:
    client = _FakeClient(outcomes=[_status_error(401, "invalid API key")])
    parser = ScheduleParser(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(AIConfigurationError, match="Ошибка конфигурации модели"):
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert len(client.chat.completions.calls) == 1
    assert client.chat.completions.calls[0]["model"] == "gemini-2.0-flash"


def test_404_from_primary_and_fallback_is_reported_as_configuration_error() -> None:
    client = _FakeClient(
        outcomes=[
            _status_error(404, "primary model not found"),
            _status_error(404, "fallback model not found"),
        ]
    )
    parser = ScheduleParser(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(AIConfigurationError, match="Ошибка конфигурации модели"):
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert [call["model"] for call in client.chat.completions.calls] == [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]


def test_primary_404_is_not_masked_by_temporary_fallback_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parser_module.time, "sleep", lambda _: None)
    client = _FakeClient(
        outcomes=[
            _status_error(404, "primary model not found"),
            *[_status_error(503, "fallback model unavailable") for _ in range(4)],
        ]
    )
    parser = ScheduleParser(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(AIConfigurationError, match="Ошибка конфигурации модели"):
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))


def test_json_mode_fallback_only_for_schema_unsupported_bad_request() -> None:
    client = _FakeClient(
        outcomes=[
            _status_error(
                400,
                "response_format json_schema is not supported",
                error_type=BadRequestError,
            ),
            _FakeResponse('{"events": []}'),
        ]
    )
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert len(client.chat.completions.calls) == 2
    first_format = client.chat.completions.calls[0]["response_format"]
    second_format = client.chat.completions.calls[1]["response_format"]
    assert first_format["type"] == "json_schema"
    assert second_format == {"type": "json_object"}


def test_json_mode_fallback_does_not_hide_unrelated_bad_request() -> None:
    client = _FakeClient(
        outcomes=[
            _status_error(
                400,
                "invalid response_format json_schema payload",
                error_type=BadRequestError,
            )
        ]
    )
    parser = ScheduleParser(api_key="test-key", client=client)  # type: ignore[arg-type]

    with pytest.raises(BadRequestError):
        parser.parse_text("Понедельник: Матанализ", date(2026, 9, 20))

    assert len(client.chat.completions.calls) == 1


def test_api_maps_provider_unavailable_to_retryable_503() -> None:
    response = _map_ai_errors(AIProviderUnavailableError(503))

    assert response.status_code == 503
    assert "временно перегружен" in response.detail
    assert "через минуту" in response.detail


def test_api_preserves_model_configuration_error_message() -> None:
    response = _map_ai_errors(AIConfigurationError())

    assert response.status_code == 502
    assert str(AIConfigurationError()) == response.detail
