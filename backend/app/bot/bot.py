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
from datetime import datetime, timezone

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

CB_ADD_ALL = "cal_add_all"
CB_CANCEL = "cal_cancel"


class AddEventsState(StatesGroup):
    """Ожидание подтверждения добавления распознанных событий."""

    confirm = State()


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


def _format_preview(response: ScheduleParseResponse) -> str:
    """Человекочитаемое превью распознанных занятий."""
    lines = [f"Распознано занятий: {len(response.events)}\n"]
    for event in response.events:
        type_label = TYPE_LABELS.get(event.event_type, event.event_type.value)
        line = (
            f"🕐 {event.start_time:%H:%M}–{event.end_time:%H:%M} "
            f"| {type_label} | {event.title}"
        )
        details = []
        if event.location:
            details.append(f"📍 {event.location}")
        if event.teacher:
            details.append(f"👤 {event.teacher}")
        if details:
            line += "\n   " + "  ".join(details)
        lines.append(line)
    return "\n".join(lines)


async def _get_user_by_telegram_id(telegram_id: int) -> User | None:
    async with async_session_factory() as session:
        return await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )


async def _process_schedule(
    message: Message, state: FSMContext, response: ScheduleParseResponse
) -> None:
    """Общий финал фото/войс-хэндлеров: превью + кнопки подтверждения."""
    if not response.events:
        await message.answer(
            "Не удалось распознать занятия. Попробуйте более чёткое фото "
            "или добавьте события вручную в приложении."
        )
        return
    await state.set_state(AddEventsState.confirm)
    await state.update_data(
        events=[e.model_dump(mode="json") for e in response.events]
    )
    await message.answer(_format_preview(response), reply_markup=_keyboard())


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
            "❌ Ссылка недействительна или истекла. "
            "Получите новый токен в приложении."
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

    await message.answer("🔍 Распознаю расписание с фото…")
    try:
        photo = message.photo[-1]  # максимальное доступное разрешение
        buffer = io.BytesIO()
        await bot.download(photo.file_id, destination=buffer)
        settings = get_settings()
        response = await ai_service.parse_schedule_image(
            buffer.getvalue(),
            "image/jpeg",
            (message.date or datetime.now(timezone.utc)).date(),
            settings.bot_default_timezone,
        )
    except Exception as exc:
        logger.exception("Ошибка распознавания фото")
        await message.answer(f"❌ Ошибка распознавания: {exc}")
        return
    await _process_schedule(message, state, response)


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

    await message.answer("🎙 Распознаю голосовое сообщение…")
    try:
        buffer = io.BytesIO()
        await bot.download(message.voice.file_id, destination=buffer)
        settings = get_settings()
        transcript = await ai_service.transcribe_audio(
            buffer.getvalue(), filename="voice.oga"
        )
        response = await ai_service.parse_schedule_text(
            transcript,
            (message.date or datetime.now(timezone.utc)).date(),
            settings.bot_default_timezone,
        )
    except Exception as exc:
        logger.exception("Ошибка обработки голосового сообщения")
        await message.answer(f"❌ Ошибка распознавания: {exc}")
        return
    await _process_schedule(message, state, response)


@router.callback_query(F.data == CB_ADD_ALL, AddEventsState.confirm)
async def cb_add_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение: батч-сохранение распознанных событий."""
    telegram_id = callback.from_user.id if callback.from_user else None
    user = (
        await _get_user_by_telegram_id(telegram_id) if telegram_id else None
    )
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
            f"✅ Добавлено занятий: {len(events)}.\n"
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
