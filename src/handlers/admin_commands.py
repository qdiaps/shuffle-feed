import asyncio
import os
import logging
import zipfile
import random

from src.config_loader import config
from src.database import core as db
from src.keyboards import keyboards
from src.services import parser
from src.states import AddChannelState

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime

logger = logging.getLogger(__name__)

router = Router()

async def admin_check(user_id: int):
    logger.debug(f"Проверка на админа юзера {user_id}.")
    is_admin = await db.is_admin(user_id)
    if not is_admin and user_id != int(config.SUPER_ADMIN_ID):
        return False
    return True

async def get_user_info(bot: Bot, user_id: int):
    try:
        chat_info = await bot.get_chat(user_id)

        full_name = chat_info.full_name
        username = f"@{chat_info.username}" if chat_info.username else "Без юзернейма"

        return full_name, username
    except TelegramBadRequest:
        return "Не найден/удалён", None
    except Exception as e:
        return f"Ошибка: {e}", None

@router.message(Command("admin_help"))
async def cmd_admin_help(message: Message):
    logger.debug(f"Вывод админских команд.")
    if await admin_check(message.from_user.id) == False:
        return
    
    await message.answer(
        "Полный список админских команд\n"
        "1. /add_admin [user id] - назначить пользователя админом\n"
        "2. /remove_admin [user id] - забрать права админа\n"
        "3. /add_channel [username] - добавить канал в базу\n"
        "4. /remove_channel [username] - удалить канал\n"
        "5. /stats - показать полную статистику\n"
        "6. /logs - отправить файлы с логами"
    )

@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message, command: CommandObject, bot: Bot):
    if await admin_check(message.from_user.id) == False:
        return

    if not command.args:
        await message.answer(
            "/add_admin [user id]\n\n"
            "Например: /add_admin 861583827"
        )
        return

    if not command.args.isdigit():
        await message.answer("ID пользователя должен состоять только из цифр.")
        return
    
    new_admin_id = int(command.args)

    is_admin = await db.is_admin(new_admin_id)
    if is_admin:
        await message.answer("Пользователь уже является администратором.")
        return

    await db.add_user(new_admin_id)
    await db.add_admin(new_admin_id)

    await message.answer(f"Пользователь {new_admin_id} назначен администратором.")

    try:
        promoter_link = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'
        await bot.send_message(new_admin_id, 
                               f"Вам выданы права администратора! Назначил {promoter_link}. Посмотреть доступные команды /admin_help",
                               parse_mode="HTML")
    except Exception as e:
        await message.answer(
            f"Права выданы, но я не смог написать пользователю в ЛС (возможно, бот заблокирован)\n"
            f"Ошибка: {e}"
        )
        logger.warning(f"Не вышло отправить оповещение юзеру {new_admin_id}: {e}", exc_info=True)

@router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message, command: CommandObject, bot: Bot):
    if await admin_check(message.from_user.id) == False:
        return

    if not command.args:
        await message.answer(
            "/remove_admin [user id]\n\n"
            "Например: /remove_admin 861583827"
        )
        return

    if not command.args.isdigit():
        await message.answer("ID пользователя должен состоять только из цифр.")
        return
    
    target_id = int(command.args)
    is_admin = await db.is_admin(target_id)
    if not is_admin:
        await message.answer("Пользователь не является администратором.")
        return
    
    if target_id == int(config.SUPER_ADMIN_ID):
        await message.answer("Ну ты это, давай не делай такого больше!")
        logger.info(f"Админ {message.from_user.id} пытается забрать забрать админку у super admin {config.SUPER_ADMIN_ID}.")
        return
    
    await db.remove_admin(target_id)

    await message.answer(f"Права администратора у пользователя {target_id} отозваны.")

    try:
        demoter_link = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'
        await bot.send_message(target_id,
                               f"Вы были исключены из списка администраторов. Решение принял {demoter_link}",
                               parse_mode="HTML")
    except Exception:
        pass

@router.message(Command("add_channel"))
async def cmd_add_channel(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if await admin_check(message.from_user.id) == False:
        return
    
    if not command.args:
        await message.answer(
            "/add_channel [username]\n\n"
            "Например: /add_channel super_memes"
        )
        return
    
    raw_username = command.args.strip().split('/')[-1].replace('@', '')
    await message.answer(f"Проверяю канал @{raw_username}. Это может занять время.")

    success, preview_ids, title, channel_int_id = await parser.check_channel_and_get_preview(raw_username)

    if not success:
        await message.answer(f"Ошибка: {preview_ids}")
        logger.error(f"Ошибка при парсинге канала {raw_username}: {preview_ids}", exc_info=True)
        return
    
    target_chat_id = int(f"-100{channel_int_id}")

    await message.answer("Предпросмотр (последние 5 постов):")

    for msg_id in reversed(preview_ids):
        try:
            await bot.copy_message(chat_id=message.chat.id, from_chat_id=target_chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Не вышло скопировать сообщение {msg_id} с канала {raw_username} ({target_chat_id}).")
            
            file_path, caption, media_type = await parser.download_media_from_post(raw_username, msg_id)
            
            if file_path:
                try:
                    video_file = FSInputFile(file_path)
                    if media_type == "video":
                        await message.answer_video(video=video_file, caption=caption, parse_mode="Markdown")
                    elif media_type == "photo":
                        await message.answer_photo(photo=video_file, caption=caption, parse_mode="Markdown")
                except Exception as e:
                    await message.answer(f"Не удалось загрузить файл: {e}")
                    logger.error(f"Ошибка при загрузке файла {file_path}: {e}", exc_info=True)
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Удаление файла {file_path}.")
            else:
                await message.answer(f"<a href='https://t.me/{raw_username}/{msg_id}'>Пост #{msg_id}</a> (Бот не смог скопировать)", parse_mode="HTML")
        await asyncio.sleep(1)

    await message.answer(
        f"Найдено: {title} (@{raw_username})\n"
        f"Всё верно? Добавляем в базу?",
        reply_markup=keyboards.get_confirm_kb()
    )

    await state.update_data(username=raw_username)
    await state.set_state(AddChannelState.waiting_for_confirmation)

@router.callback_query(AddChannelState.waiting_for_confirmation, F.data == "confirm_add_channel")
async def process_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    username = data.get("username")
    
    success = await db.get_channel(username)
    
    if not success:
        await db.add_channel(username, callback.from_user.id)
        await callback.message.edit_text(
            f"Канал @{username} успешно добавлен! "
            "Запускаю фоновый парсинг всех постов... Это займет время."
        )
        asyncio.create_task(parser.full_parse(username)) 
    else:
        await callback.message.edit_text(f"Канал @{username} уже был в базе.")

    await state.clear()
    await callback.answer()

@router.callback_query(AddChannelState.waiting_for_confirmation, F.data == "cancel_add_channel")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Операция отменена.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("req_del:"))
async def process_delete_request(callback: CallbackQuery, bot: Bot):
    try:
        _, channel_username, msg_id = callback.data.split(':')
        msg_id = int(msg_id)
    except ValueError:
        await callback.answer("Ошибка данных кнопки.", show_alert=True)
        return
    
    is_admin = await db.is_admin(callback.from_user.id)

    if is_admin or callback.from_user.id == int(config.SUPER_ADMIN_ID):
        deleted = await db.delete_post(channel_username, msg_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        if deleted:
            await callback.answer("Пост удалён вами.", show_alert=True)
            logger.info(f"Админ {callback.from_user.id} удалил пост {msg_id} канала {channel_username}")
        else:
            await callback.answer("Пост уже был удалён ранее.", show_alert=True)
        return
    
    admins = await db.get_admins()
    if not admins:
        await callback.answer("Админы не найдены, некому жаловаться :(", show_alert=True)
        return
    
    admin_kb = keyboards.get_delete_post_admin_kb(channel_username, msg_id)
    post_link = f"https://t.me/{channel_username}/{msg_id}"
    report_text = (
        f"Жалоба на пост\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"От: {callback.from_user.full_name} @{callback.from_user.username} (ID: {callback.from_user.id})\n"
        f"Пост: <a href='{post_link}'>Перейти к посту</a>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Удалить из базы?"
    )

    for admin_id in admins:
        try:
            await bot.send_message(admin_id, report_text, reply_markup=admin_kb, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Не удалось отправить репорт админу {admin_id}: {e}", exc_info=True)

    await callback.answer("Жалоба отправлена администраторам.", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

@router.callback_query(F.data.startswith("mod_dec:"))
async def process_admin_decision(callback: CallbackQuery):
    try:
        parts = callback.data.split(':')
        decision = parts[1]
        channel_username = parts[2]
        msg_id = int(parts[3])
    except Exception:
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    
    await callback.message.edit_reply_markup(reply_markup=None)
    if decision == "no":
        await callback.answer("Оставлено.", show_alert=True)
    elif decision == "yes":
        is_deleted = await db.delete_post(channel_username, msg_id)

        if is_deleted:
            await callback.answer("Удалено.", show_alert=True)
        else:
            await callback.answer("Кто-то другой (или вы) уже удалил этот пост.", show_alert=True)

@router.message(Command("remove_channel"))
async def cmd_remove_channel(message: Message, command: CommandObject):
    if await admin_check(message.from_user.id) == False:
        return
    
    if not command.args:
        await message.answer(
            "/remove_channel [username]\n\n"
            "Например: /remove_channel super_memes"
        )
        return
    
    username = command.args.strip().split('/')[-1].replace('@', '')

    is_deleted = await db.remove_channel(username, message.from_user.id)

    if is_deleted:
        await message.answer(f"Канал @{username} и все его посты удалены из базы.")
    else:
        await message.answer(f"Канал @{username} не найден в базе.")

@router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot):
    if await admin_check(message.from_user.id) == False:
        return
    
    await message.answer("Начинаю сбор статистики...")

    users_stat = await db.get_users_stats()
    active_users = users_stat["active"]
    inactive_users = users_stat["inactive"]
    total_users = active_users + inactive_users

    admins_list = await db.get_admins()

    channels_data = await db.get_channels_stats()

    text = (
        f"Статистика бота\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Пользователи:\n"
        f"• Всего: {total_users}\n"
        f"• Активных: {active_users}\n"
        f"• Мёртвых: {inactive_users}\n"
    )

    await message.answer(text)

    text = (
        f"Администраторы ({len(admins_list)}):\n"
    )

    if admins_list:
        for id in admins_list:
            full_name, username = await get_user_info(bot, id)
            if not username:
                text += f"• ID: {id} - возникла ошибка (см. в логах)\n"
                logger.error(username, exc_info=True)
                continue

            text += f"• {full_name} {username} (ID {id})\n"
            await asyncio.sleep(0.5)
    else:
        text += "• База администраторов пуста"

    await message.answer(text)

    text = (
        f"Каналы ({len(channels_data)}):\n"
    )

    if channels_data:
        for username, post_count in channels_data:
            text += f"• @{username}: {post_count} постов\n"
    else:
        text += "• База каналов пуста"

    await message.answer(text)

@router.message(Command("logs"))
async def cmd_logs(message: Message):
    if await admin_check(message.from_user.id) == False:
        return
    
    log_dir = "logs"
    if not os.path.exists(log_dir):
        await message.answer("Папка с логами пуста.")
        return
    
    await message.answer("Упаковываю все логи в архив...")

    date_str = datetime.now().strftime("%Y-%m-%d")
    rand_num = random.randint(100000, 999999)
    archive_name = f"logs_{date_str}_{rand_num}.zip"
    archive_path = os.path.join(log_dir, archive_name)

    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in os.listdir(log_dir):
                if filename.startswith("bot.log"):
                    file_path = os.path.join(log_dir, filename)
                    zipf.write(file_path, arcname=filename)
        
        if os.path.exists(archive_path):
            await message.answer_document(document=FSInputFile(archive_path), caption="Полный архив логов.")
        else:
            await message.answer("Не удалось создать архив.")
    except Exception as e:
        await message.answer(f"Ошибка при создании архива: {e}")
        logger.error(f"Ошибка в /logs: {e}", exc_info=True)
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)
