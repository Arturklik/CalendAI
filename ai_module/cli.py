"""Тестовый CLI для ScheduleParser.

Примеры:
    python cli.py --image schedule.png --date 2026-09-08
    python cli.py --text "1 пара Матанализ лк, ауд. 214" --date 2026-09-08
    python cli.py --image schedule.png --date 2026-09-08 --tz +03:00
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

try:  # пакетный импорт (python -m ai_module.cli)
    from .models import EventType, ScheduleParseResponse
    from .parser import DEFAULT_TIMEZONE_OFFSET, ScheduleParser
except ImportError:  # запуск скриптом из каталога ai_module
    from models import EventType, ScheduleParseResponse
    from parser import DEFAULT_TIMEZONE_OFFSET, ScheduleParser

TYPE_LABELS = {
    EventType.lecture: "Лекция",
    EventType.practice: "Практика",
    EventType.lab: "Лабораторная",
    EventType.exam: "Экзамен",
    EventType.other: "Другое",
}

# Цвета типов занятий — как в мобильном клиенте (calendar_screen.dart).
TYPE_STYLES = {
    EventType.lecture: "blue",
    EventType.lab: "orange1",
    EventType.practice: "green",
    EventType.exam: "red",
    EventType.other: "grey62",
}

_HEADERS = ("№", "Время", "Тип", "Название", "Аудитория", "Преподаватель")


def _row(index: int, event) -> list[str]:
    return [
        str(index),
        f"{event.start_time:%H:%M}–{event.end_time:%H:%M}",
        TYPE_LABELS.get(event.event_type, event.event_type.value),
        event.title,
        event.location or "—",
        event.teacher or "—",
    ]


def print_table(response: ScheduleParseResponse) -> None:
    """Табличный вывод: rich, если установлен, иначе простой форматированный."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _print_plain(response)
        return

    table = Table(title=f"Расписание — распознано занятий: {len(response.events)}")
    for header in _HEADERS:
        table.add_column(header)
    for i, event in enumerate(response.events, start=1):
        row = _row(i, event)
        style = TYPE_STYLES.get(event.event_type)
        if style:
            row[2] = f"[{style}]{row[2]}[/{style}]"
        table.add_row(*row)
    Console().print(table)


def _print_plain(response: ScheduleParseResponse) -> None:
    print(f"Расписание — распознано занятий: {len(response.events)}")
    rows = [list(_HEADERS)] + [
        _row(i, e) for i, e in enumerate(response.events, start=1)
    ]
    widths = [max(len(r[c]) for r in rows) for c in range(len(_HEADERS))]

    def fmt(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(fmt(rows[0]))
    print("  ".join("-" * w for w in widths))
    for row in rows[1:]:
        print(fmt(row))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="calendai-parse",
        description="Распознавание расписания CalendAI через OpenAI-совместимый Vision API",
    )
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", metavar="PATH", help="путь к изображению расписания")
    source.add_argument("--text", metavar="TEXT", help="текст расписания")
    ap.add_argument("--date", required=True, metavar="YYYY-MM-DD", help="дата занятий")
    ap.add_argument(
        "--tz",
        default=DEFAULT_TIMEZONE_OFFSET,
        metavar="±HH:MM",
        help=f"часовой пояс (по умолчанию {DEFAULT_TIMEZONE_OFFSET})",
    )
    args = ap.parse_args(argv)

    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(
            f"Ошибка: некорректная дата {args.date!r}, ожидается формат YYYY-MM-DD",
            file=sys.stderr,
        )
        return 2

    try:
        parser = ScheduleParser()
        if args.image:
            response = parser.parse_image(args.image, target_date, args.tz)
        else:
            response = parser.parse_text(args.text, target_date, args.tz)
    except Exception as exc:  # сеть/авторизация/валидация — единообразно в stderr
        print(f"Ошибка распознавания: {exc}", file=sys.stderr)
        return 1

    print_table(response)
    print("\nJSON:")
    print(response.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
