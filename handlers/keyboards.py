from telegram import ReplyKeyboardMarkup

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
