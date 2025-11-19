from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core.i18n import tr
from config import ADMIN_IDS
from core.topics import TOPICS


# 🔹 Выбор языка
def kb_choose_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
    ])


def kb_settings_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="setlang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="setlang_fr")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="setlang_de")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="setlang_uk")],
    ])


# 🔹 Выбор темы
async def get_topic_keyboard(user):
    keyboard = []
    for topic_key in TOPICS.keys():
        label = await tr(user, topic_key)
        keyboard.append([KeyboardButton(label)])

    keyboard.append([KeyboardButton(await tr(user, "btn_main_menu"))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# 🔹 После выбора подтемы
async def kb_after_sub(user):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(await tr(user, "btn_search"))],
            [
                KeyboardButton(await tr(user, "btn_change_theme")),
                KeyboardButton(await tr(user, "btn_change_sub")),
            ],
            [KeyboardButton(await tr(user, "btn_main_menu"))],
            [KeyboardButton(await tr(user, "btn_support"))],
        ],
        resize_keyboard=True
    )


# 🔹 Во время поиска
async def kb_searching(user):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(await tr(user, "btn_stop"))],
            [KeyboardButton(await tr(user, "btn_change_sub"))],
            [KeyboardButton(await tr(user, "btn_main_menu"))],
            [KeyboardButton(await tr(user, "btn_support"))],
        ],
        resize_keyboard=True
    )


# 🔹 Во время чата
async def kb_chat(user):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(await tr(user, "btn_end_chat"))],
            [KeyboardButton(await tr(user, "btn_new_partner"))],
        ],
        resize_keyboard=True
    )


# 🔹 Главное меню
async def kb_main_menu(user):
    buttons = [
        [KeyboardButton(await tr(user, "btn_start_chat"))],
        [
            KeyboardButton(await tr(user, "btn_stats")),
            KeyboardButton(await tr(user, "btn_settings")),
        ],
        [
            KeyboardButton(await tr(user, "btn_suggest")),
            KeyboardButton(await tr(user, "btn_get_vip")),
        ],
        [KeyboardButton(await tr(user, "btn_donate"))],
    ]

    try:
        if int(user.get("id", 0)) in ADMIN_IDS:
            buttons.append([KeyboardButton("📊 Админ статистика")])
    except:
        pass

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# 🔹 Настройки
async def kb_settings(user):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(await tr(user, "btn_change_lang"))],
            [KeyboardButton(await tr(user, "btn_change_name"))],
            [KeyboardButton(await tr(user, "btn_change_gender"))],
            [KeyboardButton(await tr(user, "btn_main_menu"))],
        ],
        resize_keyboard=True
    )


# 🔹 Выбор пола
async def kb_gender_settings(user):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(await tr(user, "gender_male"))],
            [KeyboardButton(await tr(user, "gender_female"))],
            [KeyboardButton(await tr(user, "gender_other"))],
            [KeyboardButton(await tr(user, "settings_back"))],
        ],
        resize_keyboard=True
    )
