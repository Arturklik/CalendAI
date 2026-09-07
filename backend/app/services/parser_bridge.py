from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Optional, Union

from app.config import get_settings

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _anchor(target_date: Optional[Union[datetime, date]]) -> datetime:
    if target_date is None:
        return datetime.now(timezone.utc)
    if isinstance(target_date, datetime):
        if target_date.tzinfo is None:
            return target_date.replace(tzinfo=timezone.utc)
        return target_date
    return datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)


def _tz_offset(value: datetime) -> str:
    offset = value.utcoffset() or timedelta(0)
    total = int(offset.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _stub_response(target_date: Optional[Union[datetime, date]], *, title: str):
    from ai_module.models import EventType, ParsedCalendarEvent, ScheduleParseResponse

    start = _anchor(target_date).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=95)
    return ScheduleParseResponse(
        events=[
            ParsedCalendarEvent(
                title=(title.strip() or "Распознанное занятие")[:200],
                event_type=EventType.lecture,
                start_time=start,
                end_time=end,
                location="ауд. 312",
                teacher="Иванов И.И.",
                description="stub parse (AI_STUB=true)",
            )
        ]
    )


def get_parser():
    settings = get_settings()
    key = settings.calendai_api_key or settings.openai_api_key
    if not key:
        if settings.ai_stub:
            return None
        raise RuntimeError("CALENDAI_API_KEY / OPENAI_API_KEY is empty")
    from ai_module.parser import ScheduleParser

    return ScheduleParser(
        api_key=key,
        base_url=settings.calendai_base_url or settings.openai_base_url or None,
        model=settings.calendai_model or settings.vision_model,
    )


def parse_text(text: str, target_date: Optional[Union[datetime, date]] = None):
    parser = get_parser()
    if parser is None:
        return _stub_response(target_date, title=text.splitlines()[0] if text else "Распознанное занятие")
    anchor = _anchor(target_date)
    return parser.parse_text(text, anchor, _tz_offset(anchor))


def parse_image_file(path: str, target_date: Optional[Union[datetime, date]] = None):
    parser = get_parser()
    if parser is None:
        return _stub_response(target_date, title="Распознанное занятие")
    anchor = _anchor(target_date)
    return parser.parse_image(path, anchor, _tz_offset(anchor))
