"""Тесты форматирования распознанных занятий в Telegram-боте.

Проверяют группировку по датам, заголовки дней недели, пометку «Сегодня»
и локальную таймзону пользователя.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.bot.bot as bot_module
import pytest
from app.bot.bot import (
    CB_RETRY_RECOGNITION,
    AddEventsState,
    _count_phrase,
    _format_days_list,
    _format_preview,
    _local_date,
    _recognition_error_message,
)
from app.services import ai_service
from app.services.ai_service import AIProviderUnavailableError

from ai_module import EventType, ParsedCalendarEvent, ScheduleParseResponse


def _event(
    title: str,
    start: str,
    end: str,
    *,
    event_type: EventType = EventType.lecture,
    location: str | None = None,
    teacher: str | None = None,
) -> ParsedCalendarEvent:
    return ParsedCalendarEvent(
        title=title,
        event_type=event_type,
        start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end),
        location=location,
        teacher=teacher,
    )


def _response(*events: ParsedCalendarEvent) -> ScheduleParseResponse:
    return ScheduleParseResponse(events=list(events))


# ---------------------------------------------------------------------------
# _local_date
# ---------------------------------------------------------------------------


def test_local_date_uses_user_timezone() -> None:
    sent_at = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc)
    # 20:00 UTC — уже 21 сентября в +07:00 и ещё 20 сентября в UTC.
    assert _local_date(sent_at, "+07:00") == date(2026, 9, 21)
    assert _local_date(sent_at, "+00:00") == date(2026, 9, 20)


# ---------------------------------------------------------------------------
# _format_preview
# ---------------------------------------------------------------------------


def test_preview_single_day_shows_weekday_and_date() -> None:
    response = _response(
        _event(
            "Математический анализ",
            "2026-09-21T09:00:00+07:00",
            "2026-09-21T10:35:00+07:00",
            location="Ауд. 214",
            teacher="Иванов А.П.",
        ),
        _event(
            "Физика",
            "2026-09-21T10:50:00+07:00",
            "2026-09-21T12:25:00+07:00",
            event_type=EventType.lab,
        ),
    )

    text = _format_preview(response, today=date(2026, 9, 20), tz_offset="+07:00")

    assert "Распознано занятий: 2 на Понедельник, 21 сентября" in text
    assert "📅 Понедельник, 21 сентября" in text
    assert "🕐 09:00–10:35 | Лекция | Математический анализ" in text
    assert "📍 Ауд. 214" in text
    assert "👤 Иванов А.П." in text
    assert "Лабораторная" in text
    assert "Сегодня" not in text


def test_preview_marks_today() -> None:
    response = _response(
        _event(
            "Математический анализ",
            "2026-09-20T09:00:00+07:00",
            "2026-09-20T10:35:00+07:00",
        ),
    )

    text = _format_preview(response, today=date(2026, 9, 20), tz_offset="+07:00")

    assert "Распознано занятий: 1 на сегодня, 20 сентября" in text
    assert "📅 Сегодня, 20 сентября (воскресенье)" in text


def test_preview_groups_multiple_days_in_date_order() -> None:
    response = _response(
        _event(
            "Физика",
            "2026-09-22T10:50:00+07:00",
            "2026-09-22T12:25:00+07:00",
            event_type=EventType.practice,
        ),
        _event(
            "Математический анализ",
            "2026-09-21T09:00:00+07:00",
            "2026-09-21T10:35:00+07:00",
        ),
        _event(
            "Программирование",
            "2026-09-21T13:00:00+07:00",
            "2026-09-21T14:35:00+07:00",
        ),
    )

    text = _format_preview(response, today=date(2026, 9, 20), tz_offset="+07:00")

    assert "Распознано занятий: 3 на 2 дня" in text
    assert "📅 Понедельник, 21 сентября" in text
    assert "📅 Вторник, 22 сентября" in text
    # Дни идут по возрастанию даты.
    assert text.index("Понедельник, 21 сентября") < text.index("Вторник, 22 сентября")


def test_preview_sorts_events_within_day_by_start_time() -> None:
    response = _response(
        _event(
            "Вторая пара",
            "2026-09-21T13:00:00+07:00",
            "2026-09-21T14:35:00+07:00",
        ),
        _event(
            "Первая пара",
            "2026-09-21T09:00:00+07:00",
            "2026-09-21T10:35:00+07:00",
        ),
    )

    text = _format_preview(response, today=date(2026, 9, 20), tz_offset="+07:00")

    assert text.index("Первая пара") < text.index("Вторая пара")


def test_preview_groups_by_user_timezone() -> None:
    # 18:00 UTC — это уже 01:00 следующего дня в +07:00.
    response = _response(
        _event(
            "Ночная пара",
            "2026-09-20T18:00:00+00:00",
            "2026-09-20T19:30:00+00:00",
        ),
    )

    text = _format_preview(response, today=date(2026, 9, 20), tz_offset="+07:00")

    assert "📅 Понедельник, 21 сентября" in text
    assert "🕐 01:00–02:30" in text


def test_preview_empty_response() -> None:
    assert _format_preview(_response()) == "Не удалось распознать занятия."


# ---------------------------------------------------------------------------
# Вспомогательные форматтеры
# ---------------------------------------------------------------------------


def test_count_phrase_variants() -> None:
    today = date(2026, 9, 20)
    assert _count_phrase([date(2026, 9, 21)], today) == ("на Понедельник, 21 сентября")
    assert _count_phrase([today], today) == "на сегодня, 20 сентября"
    assert _count_phrase([date(2026, 9, 21), date(2026, 9, 22)], today) == ("на 2 дня")
    assert (
        _count_phrase([date(2026, 9, day) for day in (21, 22, 23)], today) == "на 3 дня"
    )
    assert (
        _count_phrase([date(2026, 9, day) for day in range(21, 26)], today)
        == "на 5 дней"
    )
    assert (
        _count_phrase([date(2026, 9, day) for day in range(11, 22)], today)
        == "на 11 дней"
    )
    assert (
        _count_phrase([date(2026, 9, day) for day in range(1, 22)], today)
        == "на 21 день"
    )


def test_format_days_list() -> None:
    today = date(2026, 9, 20)
    assert _format_days_list([date(2026, 9, 21)], today) == "21 сентября, Пн"
    assert _format_days_list([today], today) == "сегодня, 20 сентября"
    assert (
        _format_days_list([date(2026, 9, 21), date(2026, 9, 22)], today)
        == "21 сентября, Пн, 22 сентября, Вт"
    )


def test_preview_provider_outage_message_is_actionable() -> None:
    message = _recognition_error_message(AIProviderUnavailableError(503))

    assert "временно перегружен" in message
    assert "через минуту" in message
    assert "Error code: 503" not in message


def _fake_bot() -> SimpleNamespace:
    bot = SimpleNamespace(download=AsyncMock())

    async def download(file_id: str, destination: object) -> None:
        destination.write(b"saved telegram file")  # type: ignore[attr-defined]

    bot.download.side_effect = download
    return bot


def _retry_markup_from_answer(message: SimpleNamespace):
    markup = message.answer.await_args_list[-1].kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.text == "🔄 Повторить попытку"
    assert button.callback_data == CB_RETRY_RECOGNITION
    return markup


@pytest.mark.asyncio
async def test_handle_photo_saves_file_context_and_offers_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bot_module, "_get_user_by_telegram_id", AsyncMock(return_value=object())
    )
    monkeypatch.setattr(
        bot_module,
        "get_settings",
        lambda: SimpleNamespace(bot_default_timezone="+07:00"),
    )
    monkeypatch.setattr(
        ai_service,
        "parse_schedule_image",
        AsyncMock(side_effect=AIProviderUnavailableError(503)),
    )
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=123),
        date=datetime(2026, 9, 20, 12, tzinfo=timezone.utc),
        photo=[SimpleNamespace(file_id="telegram-photo-id")],
        answer=AsyncMock(),
    )
    state = AsyncMock()
    bot = _fake_bot()

    await bot_module.handle_photo(message, state, bot)

    state.update_data.assert_awaited_once_with(
        last_file_id="telegram-photo-id",
        media_type="photo",
        base_date="2026-09-20",
    )
    state.set_state.assert_awaited_once_with(AddEventsState.retry)
    _retry_markup_from_answer(message)


@pytest.mark.asyncio
async def test_handle_voice_saves_file_context_and_offers_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bot_module, "_get_user_by_telegram_id", AsyncMock(return_value=object())
    )
    monkeypatch.setattr(
        bot_module,
        "get_settings",
        lambda: SimpleNamespace(bot_default_timezone="+07:00"),
    )
    monkeypatch.setattr(
        ai_service,
        "transcribe_audio",
        AsyncMock(side_effect=AIProviderUnavailableError(429)),
    )
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=123),
        date=datetime(2026, 9, 20, 12, tzinfo=timezone.utc),
        voice=SimpleNamespace(file_id="telegram-voice-id"),
        answer=AsyncMock(),
    )
    state = AsyncMock()
    bot = _fake_bot()

    await bot_module.handle_voice(message, state, bot)

    state.update_data.assert_awaited_once_with(
        last_file_id="telegram-voice-id",
        media_type="voice",
        base_date="2026-09-20",
    )
    state.set_state.assert_awaited_once_with(AddEventsState.retry)
    _retry_markup_from_answer(message)


@pytest.mark.parametrize("media_type", ["photo", "voice"])
@pytest.mark.asyncio
async def test_retry_callback_redownloads_media_and_edits_to_preview(
    media_type: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_date = date(2026, 9, 20)
    response = _response(
        _event(
            "Математический анализ",
            "2026-09-20T09:00:00+07:00",
            "2026-09-20T10:35:00+07:00",
        )
    )
    monkeypatch.setattr(
        bot_module,
        "get_settings",
        lambda: SimpleNamespace(bot_default_timezone="+07:00"),
    )
    parse_image = AsyncMock(return_value=response)
    transcribe_audio = AsyncMock(return_value="расписание на понедельник")
    parse_text = AsyncMock(return_value=response)
    monkeypatch.setattr(ai_service, "parse_schedule_image", parse_image)
    monkeypatch.setattr(ai_service, "transcribe_audio", transcribe_audio)
    monkeypatch.setattr(ai_service, "parse_schedule_text", parse_text)

    state = AsyncMock()
    state.get_data.return_value = {
        "last_file_id": f"telegram-{media_type}-id",
        "media_type": media_type,
        "base_date": base_date.isoformat(),
    }
    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(message=message, answer=AsyncMock())
    bot = _fake_bot()

    await bot_module.cb_retry_recognition(callback, state, bot)

    bot.download.assert_awaited_once()
    assert bot.download.await_args.args[0] == f"telegram-{media_type}-id"
    assert (
        bot.download.await_args.kwargs["destination"].getvalue()
        == b"saved telegram file"
    )
    if media_type == "photo":
        parse_image.assert_awaited_once_with(
            b"saved telegram file", "image/jpeg", base_date, "+07:00"
        )
        transcribe_audio.assert_not_awaited()
    else:
        transcribe_audio.assert_awaited_once_with(
            b"saved telegram file", filename="voice.oga"
        )
        parse_text.assert_awaited_once_with(
            "расписание на понедельник", base_date, "+07:00"
        )

    edits = message.edit_text.await_args_list
    assert edits[0].args[0] == "⏳ Повторяю распознавание…"
    assert "Распознано занятий: 1" in edits[1].args[0]
    assert edits[1].kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "cal_add_all"
    assert callback.answer.await_count == 1
    state.set_state.assert_awaited_once_with(AddEventsState.confirm)


@pytest.mark.asyncio
async def test_retry_callback_keeps_retry_button_after_temporary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bot_module,
        "get_settings",
        lambda: SimpleNamespace(bot_default_timezone="+07:00"),
    )
    monkeypatch.setattr(
        ai_service,
        "parse_schedule_image",
        AsyncMock(side_effect=AIProviderUnavailableError(503)),
    )
    state = AsyncMock()
    state.get_data.return_value = {
        "last_file_id": "telegram-photo-id",
        "media_type": "photo",
        "base_date": "2026-09-20",
    }
    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(message=message, answer=AsyncMock())

    await bot_module.cb_retry_recognition(callback, state, _fake_bot())

    assert message.edit_text.await_args_list[0].args[0] == "⏳ Повторяю распознавание…"
    markup = message.edit_text.await_args_list[-1].kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == CB_RETRY_RECOGNITION
    state.set_state.assert_awaited_once_with(AddEventsState.retry)
