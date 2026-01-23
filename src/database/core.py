import aiosqlite
import logging

from src.config_loader import config

from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_db_connection():
    db = await aiosqlite.connect(config.DB_NAME, timeout=config.DB_TIMEOUT)
    
    try:
        await db.execute("PRAGMA journal_model=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        yield db
    finally:
        await db.close()

async def init_db():
    logger.info("Начинаю инициализацию БД.")
    async with get_db_connection() as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                added_by INTEGER,
                last_parsed_id INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_username TEXT,
                message_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
    logger.info("БД успешно инициализирована (WAL mode)")

async def add_user(user_id: int):
    logger.info(f"Добавление юзера {user_id}.")
    try:
        async with get_db_connection() as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id, is_active) VALUES (?, 1)", (user_id,))
            await db.execute("UPDATE users SET is_active = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении юзера {user_id}: {e}", exc_info=True)

async def set_user_active(user_id: int, active: bool = False):
    status = 1 if active else 0
    logger.debug(f"Смена активности юзера {user_id} на {status}.")
    try:
        async with get_db_connection() as db:
            await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (status, user_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при смене активности юзера {user_id} на {status}: {e}", exc_info=True)

async def get_active_users():
    logger.debug(f"Получение всех активных юзеров.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT user_id FROM users WHERE is_active = 1") as cursor:
                return [row[0] for row in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка при получении всех активных юзеров: {e}", exc_info=True)

async def get_inactive_users():
    logger.debug(f"Получение всех не активных юзеров.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT user_id FROM users WHERE is_active = 0") as cursor:
                return [row[0] for row in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка при получении всех не активных юзеров: {e}", exc_info=True)

async def get_users_stats():
    logger.debug(f"Получение всех юзеров для статистики.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cursor:
                active = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 0") as cursor:
                inactive = (await cursor.fetchone())[0]
        return {"active": active, "inactive": inactive}
    except Exception as e:
        logger.error(f"Ошибка при получении всех юзеров для статистики: {e}", exc_info=True)     

async def is_admin(user_id: int):
    logger.debug(f"Проверка, является ли юзер {user_id} админом.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else False
    except Exception as e:
        logger.error(f"Ошибка при проверке, является ли юзер {user_id} админом: {e}", exc_info=True)

async def get_admins():
    logger.debug(f"Получение всех админов")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT user_id FROM users WHERE is_admin = 1") as cursor:
                return [row[0] for row in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка при получении всех админов: {e}", exc_info=True)

async def add_admin(user_id: int):
    logger.info(f"Выдача юзеру {user_id} админки.")
    try:
        async with get_db_connection() as db:
            await db.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при выдаче админки юзеру {user_id}: {e}", exc_info=True)

async def remove_admin(user_id: int):
    logger.info(f"Снятие админки у юзера {user_id}.")
    try:
        async with get_db_connection() as db:
            await db.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при снятии админки у юзера {user_id}: {e}", exc_info=True)

async def get_channel(username: str):
    logger.debug(f"Получение всех каналов.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT added_by FROM channels WHERE username = ?", (username,)) as cursor:
                return await cursor.fetchone() 
    except Exception as e:
        logger.error(f"Ошибка при получении всех каналов: {e}", exc_info=True)

async def add_channel(username: str, admin_id: int):
    logger.info(f"Добавление канала {username} админом {admin_id}.")
    try:
        async with get_db_connection() as db:
            await db.execute("INSERT OR IGNORE INTO channels (username, added_by) VALUES (?, ?)", (username, admin_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении канала {username} админом {admin_id}: {e}", exc_info=True)

async def remove_channel(username: str, admin_id: int):
    logger.info(f"Удаление канала {username} админом {admin_id}.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT 1 FROM channels WHERE username = ?", (username,)) as cursor:
                if not await cursor.fetchone():
                    return False

            await db.execute("DELETE FROM posts WHERE channel_username = ?", (username,))
            await db.execute("DELETE FROM channels WHERE username = ?", (username,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Ошибка при удаление канала {username} админом {admin_id}: {e}", exc_info=True)

async def get_all_channels():
    logger.debug(f"Получение всех каналов.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT username, last_parsed_id FROM channels") as cursor:
                return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении всех каналов: {e}", exc_info=True)

async def get_channels_stats():
    logger.debug(f"Получение всех каналов и постов для статистики.")
    try:
        async with get_db_connection() as db:
            async with db.execute("""
                SELECT c.username, COUNT(p.id)
                FROM channels c
                LEFT JOIN posts p ON c.username = p.channel_username
                GROUP BY c.username
            """) as cursor:
                return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении всех каналов и постов для статистики: {e}", exc_info=True)     

async def update_channel_offset(username: str, last_id: int):
    logger.info(f"Обновление последнего айди ({last_id}) для парсинга канала {username}.")
    try:
        async with get_db_connection() as db:
            await db.execute("UPDATE channels SET last_parsed_id = ? WHERE username = ?", (last_id, username))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении последнего айди ({last_id}) для парсинга канала {username}: {e}", exc_info=True)

async def add_post(channel_username: str, message_id: int):
    logger.info(f"Добавление поста {message_id} канала {channel_username}.")
    try:
        async with get_db_connection() as db:
            await db.execute("INSERT OR IGNORE INTO posts (channel_username, message_id) VALUES (?, ?)", (channel_username, message_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении поста {message_id} канала {channel_username}: {e}", exc_info=True)

async def get_random_post():
    logger.debug(f"Получение рандомного поста.")
    try:
        async with get_db_connection() as db:
            async with db.execute("""
                SELECT channel_username, message_id 
                FROM posts 
                ORDER BY RANDOM() 
                LIMIT 1
            """) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при получении рандомного поста: {e}", exc_info=True)

async def get_all_posts():
    logger.debug(f"Получение всех постов.")
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT channel_username, message_id FROM posts") as cursor:
                return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении всех постов: {e}", exc_info=True)

async def delete_post(channel_username: str, message_id: int):
    logger.info(f"Удаление поста {message_id} с канала {channel_username}.")
    try:
        async with get_db_connection() as db: 
            async with db.execute("""
                DELETE FROM posts 
                WHERE channel_username = ? AND message_id = ?
            """, (channel_username, message_id)) as cursor:
                await db.commit()
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении поста {message_id} с канала {channel_username}: {e}", exc_info=True)