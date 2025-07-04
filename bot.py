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

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Временное хранилище пользователей
users = {}

# Актуальные темы и подкатегории
topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"],
}

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выбери тему для общения:", reply_markup=reply_markup)

# Обработчик сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if text in topics:
        users[user_id] = {"theme": text}
        keyboard = [[sub] for sub in topics[text]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=reply_markup)
        return

    if user_id in users and "theme" in users[user_id] and "sub" not in users[user_id]:
        users[user_id]["sub"] = text
        theme = users[user_id]["theme"]
        sub = users[user_id]["sub"]
        await update.message.reply_text(
            f"Отлично! Сейчас подберу тебе собеседника по теме «{theme}» — «{sub}»."
        )
        return

    await update.message.reply_text("Пожалуйста, выбери тему или подкатегорию из списка.")

# Запуск приложения
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
        webhook_url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    )
