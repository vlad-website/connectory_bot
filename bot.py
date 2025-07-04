import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
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

# Временные хранилища
users = {}  # user_id: {'theme': str, 'sub': str, 'state': str, 'partner_id': int}
waiting_users = {}  # (theme, sub): [user_id]

# Темы и подкатегории
topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"],
}

# Главное меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔄 Начать поиск собеседника"],
            ["📤 Завершить диалог"],
            ["🔙 В главное меню"],
        ],
        resize_keyboard=True,
    )

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    users[update.message.from_user.id] = {"state": "choosing_theme"}
    await update.message.reply_text("Привет! Выбери тему для общения:", reply_markup=reply_markup)

# Обработка текстовых сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {}

    user_data = users[user_id]
    state = user_data.get("state")

    # Обработка команд из главного меню
    if text == "🔄 Начать поиск собеседника":
        theme = user_data.get("theme")
        sub = user_data.get("sub")
        if not theme or not sub:
            await update.message.reply_text("Сначала выбери тему и подкатегорию.")
            return
        key = (theme, sub)
        queue = waiting_users.setdefault(key, [])
        if queue and queue[0] != user_id:
            partner_id = queue.pop(0)
            users[user_id]["partner_id"] = partner_id
            users[partner_id]["partner_id"] = user_id
            users[user_id]["state"] = "chatting"
            users[partner_id]["state"] = "chatting"

            await context.bot.send_message(partner_id, "Собеседник найден! Можете начинать общение.")
            await update.message.reply_text("Собеседник найден! Можете начинать общение.")
        else:
            queue.append(user_id)
            users[user_id]["state"] = "searching"
            await update.message.reply_text("Ищу собеседника...")

        return

    elif text == "📤 Завершить диалог":
        partner_id = user_data.get("partner_id")
        if partner_id:
            await context.bot.send_message(partner_id, "Собеседник завершил диалог.")
            users[partner_id]["state"] = "menu"
            users[partner_id].pop("partner_id", None)
        users[user_id]["state"] = "menu"
        users[user_id].pop("partner_id", None)
        await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
        return

    elif text == "🔙 В главное меню":
        users[user_id] = {"state": "choosing_theme"}
        keyboard = [[key] for key in topics.keys()]
        await update.message.reply_text("Выбери тему:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # Обработка выбора темы
    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        keyboard = [[sub] for sub in topics[text]]
        keyboard.append(["🏠 Главное меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

# Обработка выбора подкатегории
if state == "choosing_sub":
    # Возврат в главное меню
    if text == "🏠 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    # Нормальная обработка выбора подкатегории
    theme = users[user_id].get("theme")
    if theme and text in topics.get(theme, []):
        users[user_id]["sub"] = text
        users[user_id]["state"] = "menu"
        await update.message.reply_text(
            f"Отлично! Выбрана тема: «{theme}» и подкатегория: «{text}».",
            reply_markup=main_menu_keyboard()
        )
        return

    # Неправильный ввод
    await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажмите «🏠 Главное меню».")
    return

    # Обмен сообщениями между собеседниками
    if state == "chatting":
        partner_id = users[user_id].get("partner_id")
        if partner_id:
            await context.bot.send_message(partner_id, update.message.text)
        else:
            await update.message.reply_text("Собеседник не найден.")
        return

    await update.message.reply_text("Пожалуйста, выбери действие из меню.")

# Точка входа
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
