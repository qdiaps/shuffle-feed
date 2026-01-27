from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_confirm_kb():
    kb = [
        [
            InlineKeyboardButton(
                text="Добавить в базу", callback_data="confirm_add_channel"
            ),
            InlineKeyboardButton(text="Отмена", callback_data="cancel_add_channel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_delete_post_kb(channel_username: str, msg_id: int):
    kb = [
        [
            InlineKeyboardButton(
                text="Удалить из БД (ЧС)",
                callback_data=f"req_del:{channel_username}:{msg_id}",
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_delete_post_admin_kb(channel_username: str, msg_id: int):
    kb = [
        [
            InlineKeyboardButton(
                text="Удалить", callback_data=f"mod_dec:yes:{channel_username}:{msg_id}"
            ),
            InlineKeyboardButton(
                text="Оставить", callback_data=f"mod_dec:no:{channel_username}:{msg_id}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
