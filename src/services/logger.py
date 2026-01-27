import gzip
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Время | Уровень | Модуль | Сообщение
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    file_handler = RotatingFileHandler(
        "logs/bot.log", maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )

    def namer(name):
        return name + ".gz"

    def rotator(source, dest):
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                f_out.writelines(f_in)
        os.remove(source)

    file_handler.namer = namer
    file_handler.rotator = rotator

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[logging.StreamHandler(), file_handler],
    )

    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.INFO)
