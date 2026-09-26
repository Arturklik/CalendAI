"""Telegram-бот CalendAI: фото/войс -> AI -> превью пар -> сохранение.

Сценарии:
1. `/start <link_token>` — привязка telegram_id к аккаунту пользователя
   (токен выдаёт эндпоинт POST /api/v1/auth/telegram-link-token).
2. Фото/скриншот расписания -> ScheduleParser (Vision) -> превью пар
   с инлайн-кнопками «Добавить все в календарь» / «Отмена».
3. Голосовое сообщение -> Whisper -> ScheduleParser (text) -> то же превью.
4. Подтверждение -> батч-вставка в events (is_deleted=False): события
   попадут в мобильное приложение при ближайшей синхронизации.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from ai_module import EventType as AIEventType
from ai_module import ParsedCalendarEvent, ScheduleParseResponse

from ..config import get_settings
from ..database import async_session_factory
from ..models.event import Event
from ..models.user import User
from ..services import ai_service, auth_service

logger = logging.getLogger(__name__)

router = Router()

TYPE_LABELS = {
    AIEventType.lecture: "Лекция",
    AIEventType.practice: "Практика",
    AIEventType.lab: "Лабораторная",
    AIEventType.exam: "Экзамен",
    AIEventType.other: "Другое",
}

_WEEKDAYS_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)
_WEEKDAYS_SHORT_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
_MONTHS_GENITIVE_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

CB_ADD_ALL = "cal_add_all"
CB_CANCEL = "cal_cancel"
CB_RETRY_RECOGNITION = "cal_retry_recognition"


class AddEventsState(StatesGroup):
    """Ожидание подтверждения добавления распознанных событий."""

    confirm = State()
    retry = State()


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Добавить все в календарь", callback_data=CB_ADD_ALL
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CANCEL),
            ]
        ]
    )


def _retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Повторить попытку",
                    callback_data=CB_RETRY_RECOGNITION,
                )
            ]
        ]
    )


def _parse_tz_offset(offset: str) -> timezone:
    """Смещение «±HH:MM» -> timezone(timedelta)."""
    sign = -1 if offset.startswith("-") else 1
    hours, minutes = offset.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes)))


def _local_date(sent_at: datetime | None, tz_offset: str) -> date:
    """Локальная дата отправки сообщения в таймзоне пользователя."""
    moment = sent_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_parse_tz_offset(tz_offset)).date()


def _day_header(day: date, today: date) -> str:
    """«Сегодня, 20 сентября (воскресенье)» или «Понедельник, 21 сентября»."""
    date_part = f"{day.day} {_MONTHS_GENITIVE_RU[day.month - 1]}"
    if day == today:
        return f"Сегодня, {date_part} ({_WEEKDAYS_RU[day.weekday()].lower()})"
    return f"{_WEEKDAYS_RU[day.weekday()]}, {date_part}"


def _plural_days(count: int) -> str:
    """«день» / «дня» / «дней» для числа дней."""
    if 11 <= count % 100 <= 14:
        return "дней"
    last = count % 10
    if last == 1:
        return "день"
    if 2 <= last <= 4:
        return "дня"
    return "дней"


def _count_phrase(days: list[date], today: date) -> str:
    """«на Понедельник, 21 сентября» / «на сегодня, 20 сентября» / «на 3 дня»."""
    if len(days) == 1:
        day = days[0]
        if day == today:
            return f"на сегодня, {day.day} {_MONTHS_GENITIVE_RU[day.month - 1]}"
        return f"на {_day_header(day, today)}"
    return f"на {len(days)} {_plural_days(len(days))}"


def _format_days_list(days: list[date], today: date) -> str:
    """Компактный список дней: «21 сентября, Пн», «сегодня, 20 сентября»."""
    parts = []
    for day in days:
        date_part = f"{day.day} {_MONTHS_GENITIVE_RU[day.month - 1]}"
        if day == today:
            parts.append(f"сегодня, {date_part}")
        else:
            parts.append(f"{date_part}, {_WEEKDAYS_SHORT_RU[day.weekday()]}")
    return ", ".join(parts)


def _format_preview(
    response: ScheduleParseResponse,
    today: date | None = None,
    tz_offset: str | None = None,
) -> str:
    """Превью распознанных занятий с группировкой по датам.

    `today` — локальная дата отправки сообщения (для пометки «Сегодня»),
    `tz_offset` — часовой пояс пользователя (по умолчанию из настроек).
    """
    if not response.events:
        return "Не удалось распознать занятия."

    offset = tz_offset or get_settings().bot_default_timezone
    tz = _parse_tz_offset(offset)
    today = today or datetime.now(tz).date()

    groups: dict[date, list[ParsedCalendarEvent]] = {}
    for event in response.events:
        day = event.start_time.astimezone(tz).date()
        groups.setdefault(day, []).append(event)

    days = sorted(groups)
    lines = [f"Распознано занятий: {len(response.events)} {_count_phrase(days, today)}"]
    for day in days:
        lines.append("")
        lines.append(f"📅 {_day_header(day, today)}")
        for event in sorted(groups[day], key=lambda e: e.start_time):
            local_start = event.start_time.astimezone(tz)
            local_end = event.end_time.astimezone(tz)
            type_label = TYPE_LABELS.get(event.event_type, event.event_type.value)
            lines.append(
                f"🕐 {local_start:%H:%M}–{local_end:%H:%M} "
                f"| {type_label} | {event.title}"
            )
            details = []
            if event.location:
                details.append(f"📍 {event.location}")
            if event.teacher:
                details.append(f"👤 {event.teacher}")
            if details:
                lines.append("   " + "  ".join(details))
    return "\n".join(lines)


async def _get_user_by_telegram_id(telegram_id: int) -> User | None:
    async with async_session_factory() as session:
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def _process_schedule(
    message: Message,
    state: FSMContext,
    response: ScheduleParseResponse,
    base_date: date,
    *,
    edit_message: bool = False,
) -> None:
    """Общий финал фото/войс-хэндлеров: превью + кнопки подтверждения."""
    if not response.events:
        text = (
            "Не удалось распознать занятия. Попробуйте более чёткое фото "
            "или добавьте события вручную в приложении."
        )
        await state.clear()
        if edit_message:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
    await state.set_state(AddEventsState.confirm)
    await state.update_data(events=[e.model_dump(mode="json") for e in response.events])
    preview = _format_preview(response, today=base_date)
    if edit_message:
        await message.edit_text(preview, reply_markup=_keyboard())
    else:
        await message.answer(preview, reply_markup=_keyboard())


async def _recognize_media(
    bot: Bot,
    file_id: str,
    media_type: str,
    base_date: date,
) -> ScheduleParseResponse:
    """Download a previously received Telegram file and run its recognition flow."""
    if media_type not in {"photo", "voice"}:
        raise ValueError("Неизвестный тип сохранённого файла")

    settings = get_settings()
    buffer = io.BytesIO()
    await bot.download(file_id, destination=buffer)

    if media_type == "photo":
        return await ai_service.parse_schedule_image(
            buffer.getvalue(),
            "image/jpeg",
            base_date,
            settings.bot_default_timezone,
        )

    transcript = await ai_service.transcribe_audio(
        buffer.getvalue(), filename="voice.oga"
    )
    return await ai_service.parse_schedule_text(
        transcript,
        base_date,
        settings.bot_default_timezone,
    )


def _recognition_error_message(error: Exception) -> str:
    if isinstance(error, ai_service.AIConfigurationError):
        return str(error)
    if isinstance(error, ai_service.AIProviderUnavailableError):
        return (
            "⚠️ AI-провайдер временно перегружен. "
            "Попробуйте снова через минуту, нажав кнопку ниже."
        )
    return f"❌ Ошибка распознавания: {error}"


async def _present_recognition_error(
    message: Message,
    state: FSMContext,
    error: Exception,
    *,
    edit_message: bool = False,
) -> None:
    """Keep the saved media only for transient errors that can be retried."""
    if isinstance(error, ai_service.AIProviderUnavailableError):
        await state.set_state(AddEventsState.retry)
        markup = _retry_keyboard()
    else:
        await state.clear()
        markup = None

    text = _recognition_error_message(error)
    if edit_message:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Хэндлеры
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    """Приветствие + привязка аккаунта по токену из deep link."""
    link_token = command.args
    if not link_token:
        await message.answer(
            "Привет! Я бот CalendAI 📅\n\n"
            "Пришлите фото или голосовое сообщение с расписанием — "
            "я распознаю занятия и добавлю их в ваш календарь.\n\n"
            "Чтобы привязать аккаунт, получите токен в приложении "
            "и отправьте: /start <токен>"
        )
        return

    try:
        user_id = auth_service.decode_token(
            link_token, expected_purpose=auth_service.PURPOSE_TG_LINK
        )
    except auth_service.AuthError:
        await message.answer(
            "❌ Ссылка недействительна или истекла. Получите новый токен в приложении."
        )
        return

    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id is None:
        await message.answer("❌ Не удалось определить ваш Telegram ID.")
        return

    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        if user is None:
            await message.answer("❌ Пользователь не найден.")
            return
        owner = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        if owner is not None and owner.id != user.id:
            await message.answer(
                "❌ Этот Telegram-аккаунт уже привязан к другому пользователю."
            )
            return
        user.telegram_id = telegram_id
        await session.commit()

    await message.answer(
        "✅ Аккаунт успешно привязан!\n\n"
        "Теперь просто отправьте фото расписания — распознанные занятия "
        "появятся в приложении после синхронизации."
    )


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Фото расписания -> Vision API -> превью."""
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id is None or await _get_user_by_telegram_id(telegram_id) is None:
        await message.answer(
            "Сначала привяжите аккаунт: получите токен в приложении "
            "и отправьте /start <токен>."
        )
        return

    settings = get_settings()
    # Опорная дата — локальный день отправки сообщения (а не UTC-дата),
    # от неё модель отсчитывает дни недели из расписания.
    base_date = _local_date(message.date, settings.bot_default_timezone)
    photo = message.photo[-1]  # максимальное доступное разрешение
    await state.clear()
    await state.update_data(
        last_file_id=photo.file_id,
        media_type="photo",
        base_date=base_date.isoformat(),
    )

    await message.answer("🔍 Распознаю расписание с фото…")
    try:
        response = await _recognize_media(bot, photo.file_id, "photo", base_date)
    except Exception as exc:
        logger.exception("Ошибка распознавания фото")
        await _present_recognition_error(message, state, exc)
        return
    await _process_schedule(message, state, response, base_date)


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext, bot: Bot) -> None:
    """Голосовое сообщение -> Whisper -> текст -> превью."""
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id is None or await _get_user_by_telegram_id(telegram_id) is None:
        await message.answer(
            "Сначала привяжите аккаунт: получите токен в приложении "
            "и отправьте /start <токен>."
        )
        return

    settings = get_settings()
    base_date = _local_date(message.date, settings.bot_default_timezone)
    file_id = message.voice.file_id
    await state.clear()
    await state.update_data(
        last_file_id=file_id,
        media_type="voice",
        base_date=base_date.isoformat(),
    )

    await message.answer("🎙 Распознаю голосовое сообщение…")
    try:
        response = await _recognize_media(bot, file_id, "voice", base_date)
    except Exception as exc:
        logger.exception("Ошибка обработки голосового сообщения")
        await _present_recognition_error(message, state, exc)
        return
    await _process_schedule(message, state, response, base_date)


@router.callback_query(F.data == CB_RETRY_RECOGNITION, AddEventsState.retry)
async def cb_retry_recognition(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Re-download the saved photo/voice message and retry recognition."""
    message = callback.message
    if message is None or not hasattr(message, "edit_text"):
        await callback.answer("Сообщение больше недоступно.", show_alert=True)
        return

    data = await state.get_data()
    file_id = data.get("last_file_id")
    media_type = data.get("media_type")
    try:
        base_date = date.fromisoformat(str(data["base_date"]))
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await message.edit_text("Не удалось восстановить файл. Отправьте его ещё раз.")
        await callback.answer()
        return

    if not isinstance(file_id, str) or media_type not in {"photo", "voice"}:
        await state.clear()
        await message.edit_text("Не удалось восстановить файл. Отправьте его ещё раз.")
        await callback.answer()
        return

    await message.edit_text("⏳ Повторяю распознавание…")
    await callback.answer()
    try:
        response = await _recognize_media(bot, file_id, media_type, base_date)
    except Exception as exc:
        logger.exception("Ошибка повторного распознавания файла")
        await _present_recognition_error(
            message,
            state,
            exc,
            edit_message=True,
        )
        return

    await _process_schedule(
        message,
        state,
        response,
        base_date,
        edit_message=True,
    )


@router.callback_query(F.data == CB_ADD_ALL, AddEventsState.confirm)
async def cb_add_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение: батч-сохранение распознанных событий."""
    telegram_id = callback.from_user.id if callback.from_user else None
    user = await _get_user_by_telegram_id(telegram_id) if telegram_id else None
    if user is None:
        await callback.answer("Аккаунт не привязан.", show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    raw_events = data.get("events") or []
    events = [ParsedCalendarEvent.model_validate(e) for e in raw_events]
    if not events:
        await callback.answer("Список событий пуст.", show_alert=True)
        await state.clear()
        return

    # Дни, на которые добавлены занятия (в таймзоне пользователя).
    settings = get_settings()
    tz = _parse_tz_offset(settings.bot_default_timezone)
    today = datetime.now(tz).date()
    days = sorted({parsed.start_time.astimezone(tz).date() for parsed in events})

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        for parsed in events:
            session.add(
                Event(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=parsed.title,
                    event_type=parsed.event_type.value,
                    start_time=parsed.start_time,
                    end_time=parsed.end_time,
                    location=parsed.location,
                    teacher=parsed.teacher,
                    description=parsed.description,
                    recurrence_rule=None,
                    updated_at=now,
                    is_deleted=False,
                )
            )
        await session.commit()

    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            f"✅ Добавлено занятий: {len(events)} "
            f"(на {_format_days_list(days, today)}).\n"
            "Нажмите «Обновить» в приложении — они появятся в календаре."
        )
    await callback.answer()


@router.callback_query(F.data == CB_CANCEL, AddEventsState.confirm)
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена добавления."""
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text("❌ Добавление отменено.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Жизненный цикл бота
# ---------------------------------------------------------------------------


def create_bot() -> Bot:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "Telegram-бот не сконфигурирован: задайте TELEGRAM_BOT_TOKEN"
        )
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    return dispatcher


async def start_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    """Режим polling: фоновая задача рядом с FastAPI."""
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


async def setup_webhook(bot: Bot) -> None:
    """Режим webhook: регистрация URL в Telegram."""
    settings = get_settings()
    if not settings.webhook_url:
        raise RuntimeError("Для webhook-режима задайте WEBHOOK_URL")
    await bot.set_webhook(
        url=f"{settings.webhook_url.rstrip('/')}{settings.webhook_path}",
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
    )
