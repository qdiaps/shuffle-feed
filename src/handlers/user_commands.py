import logging

from src.database import core as db
from src.services import sender

from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command, CommandStart, CommandObject

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Справка\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Бот отправляет один случайны пост каждый час. "
        "Время активности: с 8:00 до 23:00 (ночью рассылка приостанавливается).\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Полный список команд:\n"
        "1. /start - включить рассылку\n"
        "2. /stop - остановить рассылку\n"
        "3. /support [текст] - отправить сообщение администратору\n"
    )

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await db.add_user(message.from_user.id)
    await message.answer("Подписка активирована. Частота вещания: 1 пост/час. Если надоест — просто жми /stop. Приятного просмотра.")
    await sender.broadcast_random_post(bot, message.from_user.id)

@router.message(Command("stop"))
async def cmd_stop(message: Message):
    await db.set_user_active(message.from_user.id, False)
    await message.answer("Подписка отключена. Данные обновлены. Жду возвращения: /start")

@router.message(Command("support"))
async def cmd_support(message: Message, command: CommandObject, bot: Bot):
    if not command.args:
        await message.answer(
            "/support [текст]\n\n"
            "Например: /support Бот не отправляет сообщения!"
        )
        return

    report_text = (
        f"Сообщение в поддержку\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"От: {message.from_user.full_name} @{message.from_user.username} (ID: {message.from_user.id})\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{command.args}"
    )

    admins = await db.get_admins()
    if not admins:
        await message.answer("Админы не найдены, некому жаловаться :(", show_alert=True)
        return

    for admin_id in admins:
        try:
            await bot.send_message(admin_id, report_text)
            await message.answer("Сообщение отправлено администраторам.")
        except Exception as e:
            await message.answer("Не удалось отправить сообщение. Попробуйте позже.")
            logger.error(f"Не удалось отправить репорт админу {admin_id}: {e}")