import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

users = {}

topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"],
}

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["🔍 Найти собеседника"], ["❌ Завершить диалог"], ["🏠 Главное меню"]],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выбери тему для общения:", reply_markup=reply_markup)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}

    state = users[user_id]["state"]

    # Главное меню из любого состояния
    if text == "🏠 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    # Выбор темы
    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        keyboard = [[sub] for sub in topics[text]]
        keyboard.append(["🏠 Главное меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=reply_markup)
        return

    # Выбор подкатегории
    if state == "choosing_sub":
        theme = users[user_id].get("theme")
        if theme and text in topics.get(theme, []):
            users[user_id]["sub"] = text
            users[user_id]["state"] = "menu"
            await update.message.reply_text(
                f"Отлично! Выбрана тема: «{theme}» и подкатегория: «{text}».",
                reply_markup=main_menu_keyboard()
            )
            return

        await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажми «🏠 Главное меню».")
        return

    # Главное меню — действия
    if state == "menu":
        if text == "🔍 Найти собеседника":
            await update.message.reply_text("Поиск собеседника...")
            return
        elif text == "❌ Завершить диалог":
            await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return
        else:
            await update.message.reply_text("Пожалуйста, выбери действие из меню.")
            return

    await update.message.reply_text("Пожалуйста, выбери тему или нажми «🏠 Главное меню».")

if name == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
