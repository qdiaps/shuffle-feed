import asyncio
import os
import logging

from src.database import core as db
from src.services import parser
from src.keyboards.keyboards import get_delete_post_kb

from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

async def broadcast_random_post(bot: Bot, specific_user_id: int|None = None):
    post = await db.get_random_post()
    if not post:
        logger.warning("Рассылка отменена: база постов пуста.")
        if specific_user_id:
            await bot.send_message(specific_user_id, "База постов пуста!")
        return
    
    channel_username, msg_id = post
    from_chat = f"@{channel_username}"
    post_link = f"https://t.me/{channel_username}/{msg_id}"

    admin_ids = []

    if specific_user_id:
        users = [specific_user_id]
        if await db.is_admin(specific_user_id):
            admin_ids.append(specific_user_id)
        logger.info(f"Рассылка для ID: {specific_user_id}")
    else:
        users = await db.get_active_users()
        admin_ids = await db.get_admins()
        logger.info(f"Рассылка для {len(users)} пользователей.")

    if not users:
        return
    
    delete_kb = get_delete_post_kb(channel_username, msg_id)
    
    downloaded_file_path = None
    cached_file_id = None
    caption_cache = None
    media_type_cache = None

    success_count = 0

    for user_id in users:
        try:
            message_sent = False

            # Если есть File ID (копирование не сработало)
            if cached_file_id:
                if media_type_cache == "video":
                    await bot.send_video(user_id, cached_file_id, caption=caption_cache, parse_mode="Markdown")
                elif media_type_cache == "photo":
                    await bot.send_photo(user_id, cached_file_id, caption=caption_cache, parse_mode="Markdown")
                message_sent = True
            
            # Пробуем стандартное копирование
            if not message_sent:
                try:
                    await bot.copy_message(chat_id=user_id, from_chat_id=from_chat, message_id=msg_id)
                    message_sent = True
                except Exception as e:
                    logger.warning(f"Ошибка копирования для {user_id}. Переход на альтернативную отправку: {e}")
                    
                    if not downloaded_file_path:
                        path, cap, m_type = await parser.download_media_from_post(channel_username, msg_id)
                        if path:
                            downloaded_file_path = path
                            caption_cache = cap
                            media_type_cache = m_type
                        else:
                            logger.error(f"Ошибка альтернативной отправки поста {msg_id}", exc_info=True)
                            continue
                    
                    input_file = FSInputFile(downloaded_file_path)
                    sent_msg = None

                    if media_type_cache == "video":
                        sent_msg = await bot.send_video(user_id, input_file, caption=caption_cache, parse_mode="Markdown")
                    elif media_type_cache == "photo":
                        sent_msg = await bot.send_photo(user_id, input_file, caption=caption_cache, parse_mode="Markdown")
                    message_sent = True

                    if sent_msg:
                        if sent_msg.video: cached_file_id = sent_msg.video.file_id
                        elif sent_msg.photo: cached_file_id = sent_msg.photo[-1].file_id
                
            if message_sent:
                success_count += 1
                await bot.send_message(
                    user_id,
                    f"<a href='{post_link}'>Источник @{channel_username}</a>",
                    reply_markup=delete_kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True 
                )
        except Exception as e:
            logger.error(f"Не удалось отправить юзеру {user_id}: {e}", exc_info=True)
            await db.set_user_active(user_id, False)
        
        await asyncio.sleep(0.05)
    
    if downloaded_file_path and os.path.exists(downloaded_file_path):
        os.remove(downloaded_file_path)
        logger.info(f"Временный файл удален: {downloaded_file_path}")

    logger.info(f"Рассылка завершена. Успешно: {success_count}/{len(users)}")