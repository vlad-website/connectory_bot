from telegram import ReplyKeyboardMarkup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core.i18n import tr
from config import ADMIN_IDS

def kb_choose_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
    ])


# 🔹 Выбор темы
async def get_topic_keyboard(user):
    from config import TOPICS  # словарь тем → подтемы

    buttons = []
    for topic in TOPICS.keys():
        buttons.append([await tr(user, f"topic_{topic}")])  # ключи в i18n: topic_<id>

    buttons.append([await tr(user, "btn_main_menu")])  # 🏠 Главное меню
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# 🔹 Выбор подтемы для выбранной темы
async def get_subtopic_keyboard(user, topic: str):
    from config import TOPICS

    subtopics = TOPICS.get(topic, [])
    buttons = []
    for sub in subtopics:
        buttons.append([await tr(user, f"sub_{sub}")])  # ключи в i18n: sub_<id>

    buttons.append([await tr(user, "btn_main_menu")])  # 🏠 Главное меню
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)



async def kb_after_sub(user):
    return ReplyKeyboardMarkup(
        [
            [await tr(user, "btn_search")],         # 🔍 Начать поиск
            [await tr(user, "btn_change_sub")],     # ♻️ Сменить подтему
            [await tr(user, "btn_main_menu")],       # 🏠 Главное меню
            [await tr(user, "btn_support")]        # ❤️ Поддержать проект
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
    buttons = [
        [await tr(user, "btn_start_chat")],
        [await tr(user, "btn_stats"), await tr(user, "btn_settings")],
        [await tr(user, "btn_suggest"), await tr(user, "btn_get_vip")],
        [await tr(user, "btn_donate")],
    ]

    # Проверяем ID юзера как int
    if int(user["id"]) in ADMIN_IDS:
        buttons.append(["📊 Админ статистика"])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
