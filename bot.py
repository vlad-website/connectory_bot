import logging
import os
import json
import asyncio

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from aiohttp import web

# --- Константы и настройки ---
ADMIN_ID = 491000185
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

users = {}
waiting_queue = asyncio.Queue()
active_chats = {}
waiting_events = {}

topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"]
}
for t in topics:
    topics[t].append("Любая подкатегория")


# --- Клавиатуры ---
def keyboard_main_menu():
    return ReplyKeyboardMarkup([["🔍 Найти собеседника"], ["❌ Завершить диалог"], ["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_subcategories(theme):
    return ReplyKeyboardMarkup([[sub] for sub in topics[theme]] + [["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_searching():
    return ReplyKeyboardMarkup([["Продлить поиск"], ["Выбрать другого партнёра"], ["⛔ Отменить поиск"], ["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_dialog():
    return ReplyKeyboardMarkup([["Найти нового собеседника"], ["❌ Завершить диалог"]], resize_keyboard=True)


# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users[user_id] = {"state": "choosing_theme"}
    logger.info(f"User {user_id} started bot.")

    msg = (
        "👋 Привет! Я бот для знакомств и общения по интересам.\n"
        "Выбирай тему и подкатегорию — я найду тебе подходящего собеседника!\n"
        "Выбери тему для общения:"
    )
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in users:
        users[user_id] = {"state": "choosing_theme"}

    state = users[user_id]["state"]
    logger.info(f"User {user_id} state: {state}, message: {text}")

    if text == "🏠 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        await update.message.reply_text("Выберите тему:", reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))
        return

    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        await update.message.reply_text("Выберите подкатегорию:", reply_markup=keyboard_subcategories(text))
        return

    if state == "choosing_sub":
        theme = users[user_id]["theme"]
        if text in topics[theme]:
            users[user_id]["sub"] = text
            users[user_id]["state"] = "menu"
            increment_stats(theme, text)
            await update.message.reply_text(f"Вы выбрали: {theme} / {text}", reply_markup=keyboard_main_menu())
        else:
            await update.message.reply_text("Выберите подкатегорию из списка.")
        return

    if state == "menu":
        if text == "🔍 Найти собеседника":
            await start_searching(update, context, user_id)
        elif text == "❌ Завершить диалог":
            await end_dialog(update, context, user_id)
        else:
            await update.message.reply_text("Выберите действие из меню.")
        return

    if state == "searching":
        if text == "⛔ Отменить поиск":
            await cancel_search(update, context, user_id)
        elif text == "Выбрать другого партнёра":
            await cancel_search(update, context, user_id)
            await start_searching(update, context, user_id)
        else:
            await update.message.reply_text("Вы уже в поиске. Подождите партнёра или отмените поиск.")
        return

    if state == "chatting":
        if text == "❌ Завершить диалог":
            await end_dialog(update, context, user_id)
        elif text == "Найти нового собеседника":
            await start_searching(update, context, user_id)
        else:
            partner_id = active_chats.get(user_id)
            if partner_id:
                await context.bot.send_message(partner_id, text=text)
        return

    await update.message.reply_text("Выберите тему или нажмите «🏠 Главное меню».")


# --- Логика поиска ---
async def start_searching(update, context, user_id):
    if users[user_id].get("state") in ["searching", "chatting"]:
        await update.message.reply_text("Вы уже ищете или в диалоге.")
        return

    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    if not theme or not sub:
        await update.message.reply_text("Сначала выберите тему и подкатегорию.")
        return

    users[user_id]["state"] = "searching"
    await waiting_queue.put(user_id)

    asyncio.create_task(search_partner_background(update, context, user_id))
    await update.message.reply_text("Поиск собеседника...", reply_markup=keyboard_searching())


async def search_partner_background(update, context, user_id):
    waiting_events[user_id] = asyncio.Event()
    await try_match_partner(user_id, context)

    try:
        await asyncio.wait_for(waiting_events[user_id].wait(), timeout=60)
    except asyncio.TimeoutError:
        await remove_from_queue(user_id)
        if users.get(user_id, {}).get("state") == "searching":
            users[user_id]["state"] = "menu"
            await context.bot.send_message(user_id, "Сейчас все заняты. Попробуйте позже.", reply_markup=keyboard_main_menu())
    finally:
        waiting_events.pop(user_id, None)


async def try_match_partner(user_id, context):
    if users[user_id].get("state") != "searching":
        return

    theme, sub = users[user_id]["theme"], users[user_id]["sub"]
    temp = []
    partner = None

    for _ in range(waiting_queue.qsize()):
        other = await waiting_queue.get()
        if other == user_id:
            temp.append(other)
            continue

        if users.get(other) and users[other]["theme"] == theme:
            sub1, sub2 = users[other]["sub"], sub
            if "Любая подкатегория" in (sub1, sub2) or sub1 == sub2:
                partner = other
                break
        temp.append(other)

    for u in temp:
        await waiting_queue.put(u)

    if partner:
        await remove_from_queue(user_id)
        await remove_from_queue(partner)
        await start_chat(context.bot, user_id, partner)


async def start_chat(bot, user1, user2):
    for uid in (user1, user2):
        users[uid]["state"] = "chatting"

    active_chats[user1] = user2
    active_chats[user2] = user1

    theme = users[user1]["theme"]
    sub1 = users[user1]["sub"]
    sub2 = users[user2]["sub"]

    sub_display = sub2 if sub1 == "Любая подкатегория" else sub1 if sub2 == "Любая подкатегория" else sub1

    for uid in (user1, user2):
        await bot.send_message(uid, f"Вы подключены. Тема: {theme}\nПодкатегория: {sub_display}", reply_markup=keyboard_dialog())

    for uid in (user1, user2):
        if uid in waiting_events:
            waiting_events[uid].set()


async def cancel_search(update, context, user_id):
    if users[user_id]["state"] == "searching":
        users[user_id]["state"] = "menu"
        await remove_from_queue(user_id)
        if user_id in waiting_events:
            waiting_events[user_id].set()
        await update.message.reply_text("Поиск отменён.", reply_markup=keyboard_main_menu())


async def end_dialog(update, context, user_id):
    if users[user_id]["state"] != "chatting":
        await update.message.reply_text("Вы не в диалоге.")
        return

    partner = active_chats.pop(user_id, None)
    users[user_id]["state"] = "menu"

    if partner:
        active_chats.pop(partner, None)
        users[partner]["state"] = "menu"
        await context.bot.send_message(partner, "Собеседник завершил диалог.", reply_markup=keyboard_main_menu())

    await update.message.reply_text("Диалог завершён.", reply_markup=keyboard_main_menu())


async def remove_from_queue(user_id):
    temp = []
    while not waiting_queue.empty():
        u = await waiting_queue.get()
        if u != user_id:
            temp.append(u)
    for u in temp:
        await waiting_queue.put(u)


# --- Статистика ---
def increment_stats(theme, sub):
    stats = {}
    if os.path.exists("stats.json"):
        with open("stats.json", "r", encoding="utf-8") as f:
            stats = json.load(f)

    stats.setdefault(theme, {})
    stats[theme][sub] = stats[theme].get(sub, 0) + 1

    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


# --- Health-check endpoint ---
async def health(request):
    return web.Response(text="OK")

# --- Webhook + Web App ---
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="ok")
    except Exception as e:
        # Логируем ошибку, чтобы понять причину 500-й ошибки
        print(f"Ошибка при обработке webhook: {e}")
        return web.Response(status=500, text="error")

async def on_startup(app):
    token = os.getenv("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")

    if not token or not webhook_url:
        print("❌ BOT_TOKEN или WEBHOOK_URL не заданы")
        return

    print(f"✅ Устанавливаю webhook: {webhook_url}")
    await application.bot.set_webhook(webhook_url)


application: Application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

web_app = web.Application()
web_app.router.add_post("/", handle_webhook)
web_app.router.add_get("/health", health)
web_app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web.run_app(web_app, port=port)
