import logging

from os import getenv
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

@dataclass
class Config:
    API_ID: str
    API_HASH: str
    BOT_TOKEN: str
    SUPER_ADMIN_ID: str
    DB_NAME: str
    DB_TIMEOUT: float

def load_config():
    logger.debug(f"Загрузка конфига.")

    api_id = getenv("API_ID")
    if not api_id:
        logger.error(f"Ошибка: API_ID не найдено в .env", exc_info=True)
        raise ValueError("API_ID не найдено в .env")
    
    api_hash = getenv("API_HASH")
    if not api_hash:
        logger.error(f"Ошибка: API_HASH не найдено в .env", exc_info=True)
        raise ValueError("API_HASH не найдено в .env")

    bot_token = getenv("BOT_TOKEN")
    if not bot_token:
        logger.error(f"Ошибка: BOT_TOKEN не найдено в .env", exc_info=True)
        raise ValueError("BOT_TOKEN не найдено в .env")
    
    super_admin_id = getenv("SUPER_ADMIN_ID")
    if not super_admin_id:
        logger.error(f"Ошибка: SUPER_ADMIN_ID не найдено в .env", exc_info=True)
        raise ValueError("SUPER_ADMIN_ID не найдено в .env")
    
    db_name = getenv("DB_NAME")
    if not super_admin_id:
        logger.error(f"Ошибка: DB_NAME не найдено в .env", exc_info=True)
        raise ValueError("DB_NAME не найдено в .env")
    
    db_timeout = getenv("DB_TIMEOUT")
    if not db_timeout:
        logger.error(f"Ошибка: DB_TIMEOUT не найдено в .env", exc_info=True)
        raise ValueError("DB_TIMEOUT не найдено в .env")
    
    return Config(
        API_ID=api_id,
        API_HASH=api_hash,
        BOT_TOKEN=bot_token,
        SUPER_ADMIN_ID=super_admin_id,
        DB_NAME=db_name,
        DB_TIMEOUT=float(db_timeout)
    )

config = load_config()