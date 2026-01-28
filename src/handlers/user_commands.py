import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from src.database import core as db
from src.services import sender

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
    if not message.from_user:
        logger.warning(
            f"Получено сообщение без user_id: chat_id = {message.chat.id}, message_id = {message.message_id}"
        )
        return

    await db.add_user(message.from_user.id)
    await message.answer(
        "Подписка активирована. Частота вещания: 1 пост/час. Если надоест — просто жми /stop. Приятного просмотра."
    )
    await sender.broadcast_random_post(bot, message.from_user.id)


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    if not message.from_user:
        logger.warning(
            f"Получено сообщение без user_id: chat_id = {message.chat.id}, message_id = {message.message_id}"
        )
        return

    await db.set_user_active(message.from_user.id, False)
    await message.answer(
        "Подписка отключена. Данные обновлены. Жду возвращения: /start"
    )


@router.message(Command("support"))
async def cmd_support(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        logger.warning(
            f"Получено сообщение без user_id: chat_id = {message.chat.id}, message_id = {message.message_id}"
        )
        return

    if not command.args:
        await message.answer(
            "/support [текст]\n\nНапример: /support Бот не отправляет сообщения!"
        )
        return

    report_text = (
        f"Сообщение в поддержку\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"От: {message.from_user.full_name} {'@' + message.from_user.username if message.from_user.username != None else '[ Нет username ]'} (ID: {message.from_user.id})\n\n"
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
        except Exception as e:
            logger.error(f"Не удалось отправить репорт админу {admin_id}: {e}")

    await message.answer("Сообщение отправлено администраторам.")
