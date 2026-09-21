"""Тесты форматирования распознанных занятий в Telegram-боте.

Проверяют группировку по датам, заголовки дней недели, пометку «Сегодня»
и локальную таймзону пользователя.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.bot.bot import (
    _count_phrase,
    _format_days_list,
    _format_preview,
    _local_date,
)

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
    assert text.index("Понедельник, 21 сентября") < text.index(
        "Вторник, 22 сентября"
    )


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
    assert (
        _format_preview(_response())
        == "Не удалось распознать занятия."
    )


# ---------------------------------------------------------------------------
# Вспомогательные форматтеры
# ---------------------------------------------------------------------------


def test_count_phrase_variants() -> None:
    today = date(2026, 9, 20)
    assert _count_phrase([date(2026, 9, 21)], today) == (
        "на Понедельник, 21 сентября"
    )
    assert _count_phrase([today], today) == "на сегодня, 20 сентября"
    assert _count_phrase([date(2026, 9, 21), date(2026, 9, 22)], today) == (
        "на 2 дня"
    )
    assert _count_phrase(
        [date(2026, 9, day) for day in (21, 22, 23)], today
    ) == "на 3 дня"
    assert _count_phrase(
        [date(2026, 9, day) for day in range(21, 26)], today
    ) == "на 5 дней"
    assert _count_phrase(
        [date(2026, 9, day) for day in range(11, 22)], today
    ) == "на 11 дней"
    assert _count_phrase(
        [date(2026, 9, day) for day in range(1, 22)], today
    ) == "на 21 день"


def test_format_days_list() -> None:
    today = date(2026, 9, 20)
    assert _format_days_list([date(2026, 9, 21)], today) == "21 сентября, Пн"
    assert _format_days_list([today], today) == "сегодня, 20 сентября"
    assert _format_days_list(
        [date(2026, 9, 21), date(2026, 9, 22)], today
    ) == "21 сентября, Пн, 22 сентября, Вт"
