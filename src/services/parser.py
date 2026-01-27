import asyncio
import logging
import os

import qrcode
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, Message

from src.config_loader import config
from src.database import core as db

logger = logging.getLogger(__name__)

client = TelegramClient("parser", config.API_ID, config.API_HASH)


async def ensure_connection():
    if not client.is_connected():
        logger.info("Подключение в telethon.")
        await client.connect()

    if not await client.is_user_authorized():
        logger.info("Авторизация в telethon.")
        qr_login = await client.qr_login()

        qr = qrcode.QRCode()
        qr.add_data(qr_login.url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

        await qr_login.wait()


def is_valid_media(message: Message):
    if message.action:
        return False

    if not (message.photo or message.video):
        return False
    return True


async def download_media_from_post(username: str, message_id: int):
    await ensure_connection()

    try:
        entity = await client.get_entity(username)
        message = await client.get_messages(entity, ids=message_id)

        if not is_valid_media(message):
            return None, None, None

        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        media_type = "video" if message.video else "photo"
        path = await client.download_media(message, file="downloads/")
        caption = message.text or ""

        logger.info(f"Установка файла {path}, тип {media_type}.")

        return path, caption, media_type
    except Exception as e:
        logger.error(f"Ошибка скачивания медиа {message_id}: {e}", exc_info=True)
        return None, None, None


async def check_channel_and_get_preview(username: str):
    await ensure_connection()

    try:
        entity = await client.get_entity(username)

        if not isinstance(entity, Channel) or entity.megagroup:
            return False, "Это не канал.", None, None

        messages_ids = []
        async for msg in client.iter_messages(entity, limit=20):
            if not is_valid_media(msg):
                continue

            messages_ids.append(msg.id)
            if len(messages_ids) >= 5:
                break
            await asyncio.sleep(0.2)

        if not messages_ids:
            return False, "Канал пуст или нет постов с фото/видео.", None, None

        return True, messages_ids, entity.title, entity.id
    except ValueError:
        return False, "Неверный username.", None, None
    except Exception as e:
        logger.error(f"Ошибка проверки канала: {e}", exc_info=True)
        return False, f"Ошибка: {e}", None, None


async def full_parse(username: str):
    await ensure_connection()

    logger.info(f"Запуск полного парсинга канала {username}.")
    entity = await client.get_entity(username)
    last_id = 0
    count = 0

    async for msg in client.iter_messages(entity, reverse=True):
        if not is_valid_media(msg):
            continue

        await db.add_post(username, msg.id)
        last_id = msg.id
        count += 1
        await asyncio.sleep(0.2)

    await db.update_channel_offset(username, last_id)
    logger.info(f"Полный парсинг {username} завершен. Добавлено {count} постов.")


async def daily_parse():
    await ensure_connection()

    logger.info("Начало ежедневного парсинга каналов.")
    channels = await db.get_all_channels()
    if not channels:
        logger.warning("Каналов в базе нет.")
        return

    count = 0

    for username, last_id in channels:
        current_max_id = last_id

        async for msg in client.iter_messages(username, min_id=last_id):
            if msg.id > current_max_id:
                current_max_id = msg.id

            if is_valid_media(msg):
                await db.add_post(username, msg.id)
                count += 1
            asyncio.sleep(0.2)

        if current_max_id > last_id:
            await db.update_channel_offset(username, current_max_id)

    logger.info(f"Ежедневный парсинг завершен. Добавлено {count} постов.")
