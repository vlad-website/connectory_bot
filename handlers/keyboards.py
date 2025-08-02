from telegram import ReplyKeyboardMarkup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core.i18n import tr

def kb_choose_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
    ])

async def kb_after_sub(user):
    return ReplyKeyboardMarkup(
        [
            [await tr(user, "btn_search")],         # 🔍 Начать поиск
            [await tr(user, "btn_change_sub")],     # ♻️ Сменить подтему
            [await tr(user, "btn_main_menu")]       # 🏠 Главное меню
        ],
        resize_keyboard=True
    )

# 🔹 Во время поиска собеседника
async def kb_searching(user):
    return ReplyKeyboardMarkup(
        [
            [await tr(user, "btn_stop")],
            [await tr(user, "btn_change_sub")],
            [await tr(user, "btn_main_menu")],
            [await tr(user, "btn_support")],
        ],
        resize_keyboard=True
    )
    

# 🔹 Во время активного чата
async def kb_chat(user):
    return ReplyKeyboardMarkup(
        [
            [await tr(user, "btn_end_chat")],
            [await tr(user, "btn_new_partner")],
        ],
        resize_keyboard=True
    )



# 🔹 Создание главного меню
async def kb_main_menu(user):
    return ReplyKeyboardMarkup(
        [
            [await tr(user, "btn_start_chat")],
            [await tr(user, "btn_stats"), await tr(user, "btn_settings")],
            [await tr(user, "btn_suggest"), await tr(user, "btn_get_vip")],
            [await tr(user, "btn_donate")],
        ],
        resize_keyboard=True
    )
