import asyncio
import logging

from src.config_loader import config
from src.database import core as db
from src.handlers import user_commands, admin_commands
from src.services import parser, sender, logger as L

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

async def main():
    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(user_commands.router)
    dp.include_router(admin_commands.router)

    scheduler = AsyncIOScheduler()

    scheduler.add_job(parser.daily_parse, "cron", hour="6", minute="0")
    scheduler.add_job(sender.broadcast_random_post, "cron", hour="8-23", minute="0", kwargs={"bot": bot})

    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    L.setup_logger()
    logger.info(f"Запуск бота.")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен руками.")