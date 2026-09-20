"""Точка входа FastAPI-приложения CalendAI.

- CORS, роутеры /api/v1/*, health-check;
- Telegram-бот живёт в том же процессе через lifespan:
  polling — фоновой задачей, webhook — через POST /tg/webhook.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import ai, auth, events, sync
from .config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск/остановка Telegram-бота вместе с приложением."""
    settings = get_settings()
    bot: Bot | None = None
    dispatcher: Dispatcher | None = None
    polling_task: asyncio.Task | None = None

    if settings.telegram_bot_token:
        from .bot.bot import (
            create_bot,
            create_dispatcher,
            setup_webhook,
            start_polling,
        )

        bot = create_bot()
        dispatcher = create_dispatcher()
        app.state.tg_bot = bot
        app.state.tg_dispatcher = dispatcher

        if settings.bot_mode == "webhook":
            await setup_webhook(bot)
            logger.info("Telegram-бот: режим webhook (%s)", settings.webhook_path)
        else:
            polling_task = asyncio.create_task(start_polling(bot, dispatcher))
            logger.info("Telegram-бот: режим polling")
    else:
        logger.warning(
            "TELEGRAM_BOT_TOKEN не задан — бот отключён, работает только API"
        )

    yield

    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if settings.telegram_bot_token and settings.bot_mode == "webhook" and bot:
        await bot.delete_webhook()
    if bot is not None:
        await bot.session.close()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_v1_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(events.router, prefix=prefix)
    app.include_router(sync.router, prefix=prefix)
    app.include_router(ai.router, prefix=prefix)

    @app.get("/health", tags=["service"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(settings.webhook_path, include_in_schema=False)
    async def telegram_webhook(request: Request) -> JSONResponse:
        """Приём обновлений Telegram в webhook-режиме."""
        settings = get_settings()
        if settings.webhook_secret:
            header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header != settings.webhook_secret:
                return JSONResponse({"ok": False}, status_code=403)
        bot: Bot = request.app.state.tg_bot
        dispatcher: Dispatcher = request.app.state.tg_dispatcher
        update = Update.model_validate(await request.json())
        await dispatcher.feed_update(bot, update)
        return JSONResponse({"ok": True})

    return app


app = create_app()
