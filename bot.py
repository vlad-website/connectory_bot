import logging
import os
from asyncio import create_task, sleep
from datetime import datetime
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
searching_users = set()
active_chats = {}
chat_history = []
topic_stats = {}

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
        [["\U0001F50D Найти собеседника"], ["\u274C Завершить диалог"], ["\U0001F3E0 Главное меню"]],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "\U0001F44B Привет! Я бот для знакомств и общения по интересам.\n"
        "Выбирай тему и подкатегорию — я найду тебе подходящего собеседника!",
        reply_markup=reply_markup
    )

def log_chat(user1, user2, theme, sub1, sub2):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_history.append({
        "user1": user1,
        "user2": user2,
        "theme": theme,
        "sub1": sub1,
        "sub2": sub2,
        "time": timestamp
    })
    topic_stats[theme] = topic_stats.get(theme, 0) + 1

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}

    state = users[user_id]["state"]

    if text == "\U0001F3E0 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        keyboard = [[sub] for sub in topics[text]]
        keyboard.append(["Любая подкатегория"])
        keyboard.append(["\U0001F3E0 Главное меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=reply_markup)
        return

    if state == "choosing_sub":
        theme = users[user_id].get("theme")
        if theme and (text in topics.get(theme, []) or text == "Любая подкатегория"):
            users[user_id]["sub"] = text
            users[user_id]["state"] = "menu"
            await update.message.reply_text(
                f"Отлично! Выбрана тема: «{theme}» и подкатегория: «{text}».",
                reply_markup=main_menu_keyboard()
            )
            return
        await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажми «\U0001F3E0 Главное меню».")
        return

    if state == "menu":
        if text == "\U0001F50D Найти собеседника":
            users[user_id]["state"] = "searching"
            searching_users.add(user_id)
            await update.message.reply_text("Поиск собеседника...")

            for uid in list(searching_users):
                if uid != user_id and users.get(uid, {}).get("state") == "searching":
                    partner_id = uid
                    searching_users.discard(user_id)
                    searching_users.discard(partner_id)
                    active_chats[user_id] = partner_id
                    active_chats[partner_id] = user_id

                    theme = users[user_id]["theme"]
                    sub1 = users[user_id]["sub"]
                    sub2 = users[partner_id]["sub"]

                    user1_sub = sub1 if sub1 != "Любая подкатегория" else sub2
                    user2_sub = sub2 if sub2 != "Любая подкатегория" else sub1

                    markup = ReplyKeyboardMarkup(
                        [["\u274C Завершить диалог"], ["\U0001F504 Найти нового собеседника"]],
                        resize_keyboard=True
                    )
                    await update.message.reply_text(
                        f"Вы подключены к собеседнику!\nТема: {theme}\nПодкатегория: {user1_sub or 'Без подкатегории'}",
                        reply_markup=markup
                    )
                    await context.bot.send_message(
                        partner_id,
                        f"Вы подключены к собеседнику!\nТема: {theme}\nПодкатегория: {user2_sub or 'Без подкатегории'}",
                        reply_markup=markup
                    )
                    users[user_id]["state"] = "chatting"
                    users[partner_id]["state"] = "chatting"

                    log_chat(user_id, partner_id, theme, sub1, sub2)
                    return

            async def timeout_wait(uid):
                await sleep(60)
                if users.get(uid, {}).get("state") == "searching":
                    searching_users.discard(uid)
                    users[uid]["state"] = "menu"
                    await context.bot.send_message(
                        uid,
                        "Похоже, сейчас все собеседники заняты.\nЧто хотите сделать?",
                        reply_markup=ReplyKeyboardMarkup(
                            [["\U0001F501 Продлить поиск"], ["\U0001F504 Выбрать другого партнёра"], ["\U0001F3E0 Главное меню"]],
                            resize_keyboard=True
                        )
                    )
            create_task(timeout_wait(user_id))
            return

        elif text == "\U0001F501 Продлить поиск":
            await update.message.reply_text("Повторный поиск собеседника...")
            await message_handler(update, context)
            return

        elif text == "\U0001F504 Выбрать другого партнёра":
            users[user_id]["state"] = "choosing_theme"
            keyboard = [[key] for key in topics.keys()]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Выберите новую тему:", reply_markup=reply_markup)
            return

        elif text == "\u274C Завершить диалог":
            await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return

        else:
            await update.message.reply_text("Пожалуйста, выбери действие из меню.")
            return

    if state == "chatting":
        if text == "\U0001F504 Найти нового собеседника" or text == "\u274C Завершить диалог":
            partner_id = active_chats.pop(user_id, None)
            if partner_id:
                active_chats.pop(partner_id, None)
                await context.bot.send_message(partner_id, "Собеседник завершил диалог.", reply_markup=main_menu_keyboard())
                users[partner_id]["state"] = "menu"
            users[user_id]["state"] = "menu"

            if text == "\U0001F504 Найти нового собеседника":
                await update.message.reply_text("Поиск нового собеседника...", reply_markup=main_menu_keyboard())
                await message_handler(update, context)
            else:
                await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return

        partner_id = active_chats.get(user_id)
        if partner_id:
            await context.bot.send_message(partner_id, text)
        return

    await update.message.reply_text("Пожалуйста, выбери тему или нажми «\U0001F3E0 Главное меню».")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
import logging
import os
from asyncio import create_task, sleep
from datetime import datetime
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
searching_users = set()
active_chats = {}
chat_history = []
topic_stats = {}

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
        [["\U0001F50D Найти собеседника"], ["\u274C Завершить диалог"], ["\U0001F3E0 Главное меню"]],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "\U0001F44B Привет! Я бот для знакомств и общения по интересам.\n"
        "Выбирай тему и подкатегорию — я найду тебе подходящего собеседника!",
        reply_markup=reply_markup
    )

def log_chat(user1, user2, theme, sub1, sub2):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_history.append({
        "user1": user1,
        "user2": user2,
        "theme": theme,
        "sub1": sub1,
        "sub2": sub2,
        "time": timestamp
    })
    topic_stats[theme] = topic_stats.get(theme, 0) + 1

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}

    state = users[user_id]["state"]

    if text == "\U0001F3E0 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        keyboard = [[sub] for sub in topics[text]]
        keyboard.append(["Любая подкатегория"])
        keyboard.append(["\U0001F3E0 Главное меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=reply_markup)
        return

    if state == "choosing_sub":
        theme = users[user_id].get("theme")
        if theme and (text in topics.get(theme, []) or text == "Любая подкатегория"):
            users[user_id]["sub"] = text
            users[user_id]["state"] = "menu"
            await update.message.reply_text(
                f"Отлично! Выбрана тема: «{theme}» и подкатегория: «{text}».",
                reply_markup=main_menu_keyboard()
            )
            return
        await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажми «\U0001F3E0 Главное меню».")
        return

    if state == "menu":
        if text == "\U0001F50D Найти собеседника":
            users[user_id]["state"] = "searching"
            searching_users.add(user_id)
            await update.message.reply_text("Поиск собеседника...")

            for uid in list(searching_users):
                if uid != user_id and users.get(uid, {}).get("state") == "searching":
                    partner_id = uid
                    searching_users.discard(user_id)
                    searching_users.discard(partner_id)
                    active_chats[user_id] = partner_id
                    active_chats[partner_id] = user_id

                    theme = users[user_id]["theme"]
                    sub1 = users[user_id]["sub"]
                    sub2 = users[partner_id]["sub"]

                    user1_sub = sub1 if sub1 != "Любая подкатегория" else sub2
                    user2_sub = sub2 if sub2 != "Любая подкатегория" else sub1

                    markup = ReplyKeyboardMarkup(
                        [["\u274C Завершить диалог"], ["\U0001F504 Найти нового собеседника"]],
                        resize_keyboard=True
                    )
                    await update.message.reply_text(
                        f"Вы подключены к собеседнику!\nТема: {theme}\nПодкатегория: {user1_sub or 'Без подкатегории'}",
                        reply_markup=markup
                    )
                    await context.bot.send_message(
                        partner_id,
                        f"Вы подключены к собеседнику!\nТема: {theme}\nПодкатегория: {user2_sub or 'Без подкатегории'}",
                        reply_markup=markup
                    )
                    users[user_id]["state"] = "chatting"
                    users[partner_id]["state"] = "chatting"

                    log_chat(user_id, partner_id, theme, sub1, sub2)
                    return

            async def timeout_wait(uid):
                await sleep(60)
                if users.get(uid, {}).get("state") == "searching":
                    searching_users.discard(uid)
                    users[uid]["state"] = "menu"
                    await context.bot.send_message(
                        uid,
                        "Похоже, сейчас все собеседники заняты.\nЧто хотите сделать?",
                        reply_markup=ReplyKeyboardMarkup(
                            [["\U0001F501 Продлить поиск"], ["\U0001F504 Выбрать другого партнёра"], ["\U0001F3E0 Главное меню"]],
                            resize_keyboard=True
                        )
                    )
            create_task(timeout_wait(user_id))
            return

        elif text == "\U0001F501 Продлить поиск":
            await update.message.reply_text("Повторный поиск собеседника...")
            await message_handler(update, context)
            return

        elif text == "\U0001F504 Выбрать другого партнёра":
            users[user_id]["state"] = "choosing_theme"
            keyboard = [[key] for key in topics.keys()]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Выберите новую тему:", reply_markup=reply_markup)
            return

        elif text == "\u274C Завершить диалог":
            await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return

        else:
            await update.message.reply_text("Пожалуйста, выбери действие из меню.")
            return

    if state == "chatting":
        if text == "\U0001F504 Найти нового собеседника" or text == "\u274C Завершить диалог":
            partner_id = active_chats.pop(user_id, None)
            if partner_id:
                active_chats.pop(partner_id, None)
                await context.bot.send_message(partner_id, "Собеседник завершил диалог.", reply_markup=main_menu_keyboard())
                users[partner_id]["state"] = "menu"
            users[user_id]["state"] = "menu"

            if text == "\U0001F504 Найти нового собеседника":
                await update.message.reply_text("Поиск нового собеседника...", reply_markup=main_menu_keyboard())
                await message_handler(update, context)
            else:
                await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
            return

        partner_id = active_chats.get(user_id)
        if partner_id:
            await context.bot.send_message(partner_id, text)
        return

    await update.message.reply_text("Пожалуйста, выбери тему или нажми «\U0001F3E0 Главное меню».")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
