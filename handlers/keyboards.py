from telegram import ReplyKeyboardMarkup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb_choose_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
    ])

def kb_after_sub():
    return ReplyKeyboardMarkup(
        [["🔍 Начать поиск"], ["Изменить подтему"], ["🏠 Главное меню"], ["❤️ Поддержать проект"]],
        resize_keyboard=True
    )

def kb_searching():
    return ReplyKeyboardMarkup(
        [["⛔ Остановить поиск"], ["Изменить подтему"], ["🏠 Главное меню"], ["❤️ Поддержать проект"]],
        resize_keyboard=True
    )

def kb_chat():
    return ReplyKeyboardMarkup(
        [["❌ Завершить диалог"], ["🔍 Новый собеседник"], ["🏠 Главное меню"], ["❤️ Поддержать проект"]],
        resize_keyboard=True
    )
