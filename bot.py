import logging
import os
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Настройка логгирования в файл
logging.basicConfig(
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ID администратора (ваш Telegram ID)
ADMIN_ID = 123456789  # замените на свой Telegram ID

users = {}
waiting_users = []
active_chats = {}
stats = {}

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
        resize_keyboard=True,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Привет! Я бот для знакомств и общения по интересам.\n\nВыберите тему, которая вам интересна:",
        reply_markup=reply_markup,
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    logging.info(f"User {user_id} sent: {text}")

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}

    state = users[user_id]["state"]

    if text == "🏠 Главное меню":
        users[user_id] = {"state": "choosing_theme"}
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        keyboard = [[sub] for sub in topics[text]]
        keyboard.append(["Любая подкатегория"])
        keyboard.append(["🏠 Главное меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=reply_markup)
        return

    if state == "choosing_sub":
        theme = users[user_id].get("theme")
        if theme:
            if text == "Любая подкатегория":
                users[user_id]["sub"] = None
            elif text in topics[theme]:
                users[user_id]["sub"] = text
            else:
                await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажми «🏠 Главное меню».")
                return
            users[user_id]["state"] = "menu"
            selected_sub = users[user_id]["sub"]
            await update.message.reply_text(
                f"Выбрана тема: «{theme}»{f" и подкатегория: «{selected_sub}»" if selected_sub else " (любая подкатегория)"}.",
                reply_markup=main_menu_keyboard(),
            )
            return

    if state == "menu":
        if text == "🔍 Найти собеседника":
            await update.message.reply_text("Поиск собеседника...")
            await find_partner(update, context)
            return
        elif text == "❌ Завершить диалог":
            await end_chat(user_id, context)
            await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return
        else:
            await update.message.reply_text("Пожалуйста, выбери действие из меню.")
            return

    await update.message.reply_text("Пожалуйста, выбери тему или нажми «🏠 Главное меню».")

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    for uid in waiting_users:
        if uid != user_id and users[uid].get("theme") == theme:
            if sub is None or users[uid].get("sub") is None or users[uid].get("sub") == sub:
                waiting_users.remove(uid)
                active_chats[user_id] = uid
                active_chats[uid] = user_id
                users[user_id]["state"] = "in_chat"
                users[uid]["state"] = "in_chat"
                partner_sub = users[uid].get("sub")

                # Увеличить статистику
                stats[user_id] = stats.get(user_id, 0) + 1
                stats[uid] = stats.get(uid, 0) + 1

                for uid1 in [user_id, uid]:
                    msg = f"Вы соединены по теме «{theme}»"
                    other_sub = users[uid2 := active_chats[uid1]].get("sub")
                    if other_sub:
                        msg += f" и подкатегории «{other_sub}»"
                    await context.bot.send_message(uid1, msg)
                return

    waiting_users.append(user_id)
    await asyncio.sleep(60)
    if user_id in waiting_users:
        waiting_users.remove(user_id)
        keyboard = [["🔍 Продолжить поиск"], ["🏠 Главное меню"]]
        await update.message.reply_text(
            "Сейчас все собеседники заняты или не удалось найти подходящего. Что дальше?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        users[user_id]["state"] = "menu"

async def end_chat(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        await context.bot.send_message(partner_id, "Ваш собеседник завершил диалог.", reply_markup=main_menu_keyboard())
        users[partner_id]["state"] = "menu"
    users[user_id]["state"] = "menu"

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    message = "📊 Статистика пользователей:\n"
    for uid, count in stats.items():
        message += f"👤 {uid}: {count} поисков\n"
    await update.message.reply_text(message or "Нет статистики.")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
