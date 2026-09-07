from __future__ import annotations

import io
import logging
from typing import Optional

import httpx
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("calendai.bot")

API_BASE = "http://127.0.0.1:8000/api/v1"
BOT_KEY = "dev-bot-key-change-me"

PENDING: dict[int, list[dict]] = {}
TOKENS: dict[int, str] = {}

BTN_EVENTS = "Мои занятия"
BTN_ADD = "Добавить расписание"
BTN_HELP = "Помощь"


def _load_settings() -> None:
    global API_BASE, BOT_KEY
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root / "backend"))
    from app.config import get_settings

    settings = get_settings()
    API_BASE = settings.api_base_url.rstrip("/") + "/api/v1"
    BOT_KEY = settings.bot_api_key


def _menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_ADD)],
            [KeyboardButton(BTN_EVENTS), KeyboardButton(BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Добавить в календарь", callback_data="confirm"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ]
        ]
    )


def _headers(telegram_id: int) -> dict[str, str]:
    token = TOKENS.get(telegram_id)
    if not token:
        raise RuntimeError("not authenticated")
    return {"Authorization": f"Bearer {token}"}


async def _upsert(telegram_id: int, display_name: Optional[str]) -> dict:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{API_BASE}/auth/telegram",
                    json={"telegram_id": telegram_id, "display_name": display_name},
                    headers={"X-Bot-Key": BOT_KEY},
                )
                response.raise_for_status()
                data = response.json()
            TOKENS[telegram_id] = data["access_token"]
            return data["user"]
        except Exception as exc:
            last_error = exc
            log.warning("auth/telegram failed: %s", exc)
    raise RuntimeError(f"Не удалось связаться с сервером: {last_error}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    name = update.effective_user.first_name or "друг"
    try:
        await _upsert(update.effective_user.id, update.effective_user.full_name)
        extra = ""
    except Exception as exc:
        log.exception("start upsert")
        extra = f"\n\nСервер пока не ответил ({exc}). Напиши /start ещё раз через пару секунд."
    await update.message.reply_text(
        f"Здравствуйте, {name}!\n\n"
        "Я бот CalendAI. Пришлите фото расписания или текст пары — "
        "я распознаю занятия и предложу добавить их в календарь.\n\n"
        "Кнопки внизу:\n"
        f"• {BTN_ADD} — как отправить расписание\n"
        f"• {BTN_EVENTS} — что уже сохранено\n\n"
        "Или просто напишите, например:\n"
        "1 пара Матанализ лк, ауд. 214"
        f"{extra}",
        reply_markup=_menu(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Как добавить расписание:\n"
        "1. Пришлите фото таблицы или текст.\n"
        "2. Появится превью занятий и кнопка «Добавить в календарь».\n"
        "3. Нажмите её — пары запишутся.\n\n"
        f"{BTN_EVENTS} показывает уже сохранённые занятия.",
        reply_markup=_menu(),
    )


async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    try:
        await _upsert(update.effective_user.id, update.effective_user.full_name)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE}/events",
                headers=_headers(update.effective_user.id),
            )
            response.raise_for_status()
            events = response.json()
    except Exception as exc:
        log.exception("list events")
        await update.message.reply_text(
            f"Не получилось загрузить занятия. Напишите /start и попробуйте снова.\n{exc}",
            reply_markup=_menu(),
        )
        return
    if not events:
        await update.message.reply_text(
            "Пока занятий нет.\n"
            "Пришлите фото расписания или текст пары — затем нажмите "
            "«Добавить в календарь» под превью.",
            reply_markup=_menu(),
        )
        return
    lines = ["Ваши занятия:"]
    for item in events[:20]:
        lines.append(
            f"• {item['start_time'][:16]} {item['title']} ({item.get('location') or '—'})"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=_menu())


def _format_preview(events: list[dict]) -> str:
    if not events:
        return "Ничего не распознано. Попробуйте другую формулировку или фото."
    lines = ["Распознанные события. Если всё верно — нажмите кнопку ниже:"]
    for index, item in enumerate(events, start=1):
        lines.append(
            f"{index}. {item['title']} [{item.get('event_type')}]\n"
            f"   {item['start_time']} → {item['end_time']}\n"
            f"   {item.get('location') or '—'} / {item.get('teacher') or '—'}"
        )
    return "\n".join(lines)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None or not update.message.text:
        return
    text = update.message.text.strip()
    if text == BTN_EVENTS:
        await list_events(update, context)
        return
    if text in {BTN_ADD, BTN_HELP}:
        await help_cmd(update, context)
        return

    telegram_id = update.effective_user.id
    try:
        await _upsert(telegram_id, update.effective_user.full_name)
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{API_BASE}/ai/parse-text",
                json={"text": text},
                headers=_headers(telegram_id),
            )
        if response.status_code == 403:
            await update.message.reply_text(
                "Лимит ИИ на этой неделе исчерпан.",
                reply_markup=_menu(),
            )
            return
        response.raise_for_status()
        events = response.json().get("events", [])
    except Exception as exc:
        log.exception("parse text")
        await update.message.reply_text(
            f"Не удалось распознать текст. Напишите /start и попробуйте ещё раз.\n{exc}",
            reply_markup=_menu(),
        )
        return

    PENDING[telegram_id] = events
    markup = _confirm_keyboard() if events else _menu()
    await update.message.reply_text(_format_preview(events), reply_markup=markup)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None or not update.message.photo:
        return
    telegram_id = update.effective_user.id
    try:
        await _upsert(telegram_id, update.effective_user.full_name)
        photo = update.message.photo[-1]
        file = await photo.get_file()
        buffer = io.BytesIO()
        await file.download_to_memory(buffer)
        buffer.seek(0)
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{API_BASE}/ai/parse-image",
                headers=_headers(telegram_id),
                files={"file": ("schedule.jpg", buffer, "image/jpeg")},
            )
        if response.status_code == 403:
            await update.message.reply_text(
                "Лимит ИИ на этой неделе исчерпан.",
                reply_markup=_menu(),
            )
            return
        response.raise_for_status()
        events = response.json().get("events", [])
    except Exception as exc:
        log.exception("parse photo")
        await update.message.reply_text(
            f"Не удалось разобрать фото. Попробуйте ещё раз или пришлите текст.\n{exc}",
            reply_markup=_menu(),
        )
        return

    PENDING[telegram_id] = events
    markup = _confirm_keyboard() if events else _menu()
    await update.message.reply_text(_format_preview(events), reply_markup=markup)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.from_user is None:
        return
    await query.answer()
    telegram_id = query.from_user.id
    if query.data == "cancel":
        PENDING.pop(telegram_id, None)
        await query.edit_message_text("Отменено.")
        return
    events = PENDING.get(telegram_id) or []
    if not events:
        await query.edit_message_text("Нечего добавлять. Пришлите расписание ещё раз.")
        return
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE}/ai/confirm",
                json={"events": events},
                headers=_headers(telegram_id),
            )
            response.raise_for_status()
        PENDING.pop(telegram_id, None)
        await query.edit_message_text(f"Добавлено занятий: {len(response.json())}")
    except Exception as exc:
        log.exception("confirm")
        await query.edit_message_text(f"Не удалось сохранить: {exc}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Здравствуйте! Что-то пошло не так. Напишите /start ещё раз.",
            reply_markup=_menu(),
        )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Приветствие и меню"),
            BotCommand("events", "Мои занятия"),
            BotCommand("help", "Как добавить расписание"),
        ]
    )


def main() -> None:
    _load_settings()
    from app.config import get_settings

    token = get_settings().telegram_bot_token
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty. Put it in backend/.env")

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    application.add_error_handler(on_error)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("events", list_events))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    log.info("Bot polling started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
