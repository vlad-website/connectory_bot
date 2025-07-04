import logging
import os
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import asyncio

ADMIN_ID = 491000185

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
)
logger = logging.getLogger(__name__)

users = {}
waiting_users = []
active_chats = {}

topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"],
}

for theme in topics:
    if "Любая подкатегория" not in topics[theme]:
        topics[theme].append("Любая подкатегория")

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["🔍 Найти собеседника"], ["❌ Завершить диалог"], ["🏠 Главное меню"]],
        resize_keyboard=True,
    )

def subcategories_keyboard(theme):
    keyboard = [[sub] for sub in topics[theme]]
    keyboard.append(["🏠 Главное меню"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def searching_options_keyboard():
    return ReplyKeyboardMarkup(
        [["Продлить поиск"], ["Выбрать другого партнёра"], ["🏠 Главное меню"]],
        resize_keyboard=True,
    )

def dialog_keyboard():
    return ReplyKeyboardMarkup(
        [["Найти нового собеседника"], ["❌ Завершить диалог"]],
        resize_keyboard=True,
    )

def cancel_search_keyboard():
    return ReplyKeyboardMarkup(
        [["⛔ Отменить поиск"]],
        resize_keyboard=True,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    description = (
        "👋 Привет! Я бот для знакомств и общения по интересам.\n"
        "Выбирай тему и подкатегорию — я найду тебе подходящего собеседника!\n"
        "Выбери тему для общения:"
    )
    keyboard = [[key] for key in topics.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(description, reply_markup=reply_markup)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}
    state = users[user_id]["state"]

    if text == "🏠 Главное меню":
        if user_id in waiting_users:
            waiting_users.remove(user_id)
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    if text == "⛔ Отменить поиск":
        if user_id in waiting_users:
            waiting_users.remove(user_id)
        users[user_id]["state"] = "menu"
        await update.message.reply_text("Поиск отменён.", reply_markup=main_menu_keyboard())
        return

    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=subcategories_keyboard(text))
        return

    if state == "choosing_sub":
        theme = users[user_id].get("theme")
        if theme and text in topics.get(theme, []):
            users[user_id]["sub"] = text
            users[user_id]["state"] = "menu"
            await update.message.reply_text(
                f"Отлично! Выбрана тема: «{theme}» и подкатегория: «{text}».",
                reply_markup=main_menu_keyboard(),
            )
            increment_stats(theme, text)
            return
        await update.message.reply_text("Пожалуйста, выбери подкатегорию из списка или нажми «🏠 Главное меню».")
        return

    if state == "menu":
        if text == "🔍 Найти собеседника":
            await start_searching(update, context, user_id)
            return
        elif text == "❌ Завершить диалог":
            await end_dialog(update, context, user_id)
            return
        else:
            await update.message.reply_text("Пожалуйста, выбери действие из меню.")
            return

    if state == "chatting":
        if text == "Найти нового собеседника":
            await start_searching(update, context, user_id)
            return
        elif text == "❌ Завершить диалог":
            await end_dialog(update, context, user_id)
            return
        else:
            partner_id = active_chats.get(user_id)
            if partner_id:
                await context.bot.send_message(chat_id=partner_id, text=text)
            return

    await update.message.reply_text("Пожалуйста, выбери тему или нажми «🏠 Главное меню».")

async def start_searching(update, context, user_id):
    state = users[user_id]["state"]
    if state == "searching":
        await update.message.reply_text("Вы уже ищете собеседника...")
        return
    if state == "chatting":
        await update.message.reply_text("Вы уже в диалоге. Нажмите «❌ Завершить диалог» для выхода.")
        return

    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    if not theme or not sub:
        await update.message.reply_text("Сначала выберите тему и подкатегорию.")
        return

    users[user_id]["state"] = "searching"
    waiting_users.append(user_id)
    await update.message.reply_text("Поиск собеседника...", reply_markup=cancel_search_keyboard())

    partner_id = find_partner(user_id)
    if partner_id:
        await start_chat(update, context, user_id, partner_id)
        return

    try:
        await asyncio.wait_for(wait_for_partner(user_id), timeout=60)
    except asyncio.TimeoutError:
        if users[user_id]["state"] == "searching":
            await update.message.reply_text(
                "Сейчас все собеседники заняты, не удалось найти свободного партнёра.",
                reply_markup=searching_options_keyboard(),
            )

async def wait_for_partner(user_id):
    while users.get(user_id, {}).get("state") == "searching" and user_id in waiting_users:
        await asyncio.sleep(1)

def find_partner(user_id):
    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    for other_id in waiting_users:
        if other_id == user_id:
            continue
        if users[other_id].get("theme") == theme:
            other_sub = users[other_id].get("sub")
            if sub == "Любая подкатегория" or other_sub == "Любая подкатегория" or sub == other_sub:
                waiting_users.remove(user_id)
                waiting_users.remove(other_id)
                return other_id
    return None

async def start_chat(update, context, user_id, partner_id):
    users[user_id]["state"] = "chatting"
    users[partner_id]["state"] = "chatting"
    active_chats[user_id] = partner_id
    active_chats[partner_id] = user_id

    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")
    partner_sub = users[partner_id].get("sub")

    if sub == "Любая подкатегория" and partner_sub != "Любая подкатегория":
        sub_display = partner_sub
    elif partner_sub == "Любая подкатегория" and sub != "Любая подкатегория":
        sub_display = sub
    elif sub == "Любая подкатегория" and partner_sub == "Любая подкатегория":
        sub_display = "Любая подкатегория"
    else:
        sub_display = sub

    msg = f"Вы подключены к собеседнику.\nТема: «{theme}»\nПодкатегория: «{sub_display}»"

    await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=dialog_keyboard())
    await context.bot.send_message(chat_id=partner_id, text=msg, reply_markup=dialog_keyboard())

async def end_dialog(update, context, user_id):
    state = users[user_id]["state"]
    if state == "chatting":
        partner_id = active_chats.get(user_id)
        if partner_id:
            await context.bot.send_message(chat_id=partner_id, text="Собеседник завершил диалог.", reply_markup=main_menu_keyboard())
            users[partner_id]["state"] = "menu"
            active_chats.pop(partner_id, None)
        active_chats.pop(user_id, None)
        users[user_id]["state"] = "menu"
        await update.message.reply_text("Диалог завершён.", reply_markup=main_menu_keyboard())
    elif state == "searching":
        if user_id in waiting_users:
            waiting_users.remove(user_id)
        users[user_id]["state"] = "menu"
        await update.message.reply_text("Поиск прерван.", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("Вы не в диалоге.")

def increment_stats(theme, sub):
    try:
        with open("stats.json", "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        stats = {}

    if theme not in stats:
        stats[theme] = {}
    if sub not in stats[theme]:
        stats[theme][sub] = 0
    stats[theme][sub] += 1

    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    try:
        with open("stats.json", "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception:
        await update.message.reply_text("Не удалось загрузить статистику.")
        return

    if not stats:
        await update.message.reply_text("Статистика пока пуста.")
        return

    response = "📊 *Статистика популярности:*\n\n"
    for theme, subs in stats.items():
        total_theme = sum(subs.values())
        response += f"• *{theme}* — {total_theme} выборов\n"
        for sub, count in subs.items():
            response += f"    - {sub}: {count}\n"
        response += "\n"

    await update.message.reply_text(response, parse_mode="Markdown")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
