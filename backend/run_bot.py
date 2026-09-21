"""Автономный запуск Telegram-бота CalendAI с подробным выводом ошибок."""

from __future__ import annotations

import asyncio
import logging
import sys

from app.bot.bot import create_bot, create_dispatcher
from app.config import get_settings


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = get_settings()

    if not settings.telegram_bot_token:
        print("ОШИБКА: TELEGRAM_BOT_TOKEN не задан в backend/.env!")
        sys.exit(1)

    print("Подключаюсь к серверам Telegram (api.telegram.org)...")
    try:
        bot = create_bot()
        me = await bot.get_me()
        print(f"✅ УСПЕХ: Бот @{me.username} успешно авторизован!")
        print("Запускаю режим polling... Напишите боту /start в Telegram.")
        dispatcher = create_dispatcher()
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    except Exception as exc:
        print(f"\n❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {exc}")
        print("\nВозможные причины:")
        print("1. Блокировка api.telegram.org провайдером — включите VPN на компьютере.")
        print("2. Неверный токен бота в backend/.env.")
    finally:
        if "bot" in locals():
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
