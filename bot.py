# main.py
import os
import logging
import asyncio
from enum import Enum
from aiohttp import web

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from db import (
    init_db, get_user, create_user, update_user_state,
    update_user_nickname, update_user_gender, update_user_topic
)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Enums ---
class State(str, Enum):
    NICKNAME = "nickname"
    GENDER = "gender"
    THEME = "choosing_theme"
    SUB = "choosing_sub"
    MENU = "menu"
    SEARCHING = "searching"
    CHATTING = "chatting"

# --- Topics ---
topics = {
    "IT": ["Программирование", "Дизайн", "AI", "Карьера в IT"],
    "Психология": ["Самооценка", "Тревожность", "Отношения", "Мотивация"],
    "Хобби": ["Игры", "Путешествия", "Книги", "Музыка"],
    "Бизнес": ["Стартапы", "Поиск партнёров", "Маркетинг", "Финансы"],
    "Культура и искусство": ["Фильмы", "Литература", "Живопись", "Фотография"],
    "Здоровье и спорт": ["Фитнес", "Питание", "Медитация", "ЗОЖ"]
}
for sub in topics.values():
    sub.append("Любая подкатегория")

# --- In-memory ---
waiting_queue = asyncio.Queue()
active_chats = {}
waiting_events = {}
locks = {}

# --- Keyboards ---
def keyboard_main():
    return ReplyKeyboardMarkup(
        [["🔍 Найти собеседника", "❌ Завершить диалог"], ["🏠 Главное меню"]],
        resize_keyboard=True
    )

def keyboard_subcategories(theme):
    return ReplyKeyboardMarkup([[sub] for sub in topics.get(theme, [])] + [["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_searching():
    return ReplyKeyboardMarkup(
        [["Продлить поиск"], ["Выбрать другого партнёра"], ["⛔ Отменить поиск"], ["🏠 Главное меню"]],
        resize_keyboard=True
    )

def keyboard_chat():
    return ReplyKeyboardMarkup(
        [["Найти нового собеседника"], ["❌ Завершить диалог"]],
        resize_keyboard=True
    )

# --- Utils ---
def get_lock(uid):
    if uid not in locks:
        locks[uid] = asyncio.Lock()
    return locks[uid]

# --- Core Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if user:
        nickname = user["nickname"] or "друг"
        await update.message.reply_text(f"👋 С возвращением, {nickname}!", reply_markup=keyboard_main())
    else:
        await create_user(user_id)
        await update_user_state(user_id, State.NICKNAME)
        await update.message.reply_text("👋 Привет! Введи свой ник (до 32 символов):")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = await get_user(user_id)

    if not user:
        await create_user(user_id)
        await update_user_state(user_id, State.NICKNAME)
        await update.message.reply_text("👋 Привет! Введи свой ник:")
        return

    state = user["state"]
    logger.info(f"User {user_id} state: {state}, message: {text}")

    try:
        if text == "🏠 Главное меню":
            await update_user_state(user_id, State.THEME)
            await update.message.reply_text("Выберите тему:", reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))
            return

        if state == State.NICKNAME:
            await update_user_nickname(user_id, text[:32])
            await update_user_state(user_id, State.GENDER)
            await update.message.reply_text(
                f"Спасибо, {text[:32]}! Теперь выбери свой пол:",
                reply_markup=ReplyKeyboardMarkup([
                    ["Мужской"], ["Женский"], ["Не указывать"]
                ], resize_keyboard=True)
            )
            return

        if state == State.GENDER:
            if text not in ["Мужской", "Женский", "Не указывать"]:
                await update.message.reply_text("Выберите пол из списка.")
                return
            await update_user_gender(user_id, text)
            await update_user_state(user_id, State.THEME)
            await update.message.reply_text("Теперь выберите тему:", reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))
            return

        if state == State.THEME and text in topics:
            await update_user_topic(user_id, theme=text)
            await update_user_state(user_id, State.SUB)
            await update.message.reply_text("Выберите подкатегорию:", reply_markup=keyboard_subcategories(text))
            return

        if state == State.SUB:
            user_theme = user["theme"]
            if text in topics.get(user_theme, []):
                await update_user_topic(user_id, sub=text)
                await update_user_state(user_id, State.MENU)
                await update.message.reply_text(f"Вы выбрали: {user_theme} / {text}", reply_markup=keyboard_main())
            else:
                await update.message.reply_text("Выберите подкатегорию из списка.")
            return

        if state == State.MENU:
            if text == "🔍 Найти собеседника":
                await begin_search(update, context, user_id)
            elif text == "❌ Завершить диалог":
                await finish_dialog(update, context, user_id)
            else:
                await update.message.reply_text("Выберите действие из меню.")
            return

        if state == State.SEARCHING:
            if text == "⛔ Отменить поиск":
                await cancel_search(update, context, user_id)
            elif text == "Выбрать другого партнёра":
                await cancel_search(update, context, user_id)
                await begin_search(update, context, user_id)
            else:
                await update.message.reply_text("Ожидание партнёра. Подождите или отмените поиск.")
            return

        if state == State.CHATTING:
            if text == "❌ Завершить диалог":
                await finish_dialog(update, context, user_id)
            elif text == "Найти нового собеседника":
                await begin_search(update, context, user_id)
            else:
                partner_id = active_chats.get(user_id)
                if partner_id:
                    await context.bot.send_message(partner_id, text=text)
            return

        await update.message.reply_text("Выберите действие или нажмите '🏠 Главное меню'.")

    except Exception as e:
        logger.error(f"Ошибка в обработчике сообщений: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# --- Search System ---
async def begin_search(update, context, user_id):
    user = await get_user(user_id)
    if not user.get("theme") or not user.get("sub"):
        await update.message.reply_text("Сначала выберите тему и подкатегорию.")
        return

    await update_user_state(user_id, State.SEARCHING)
    await waiting_queue.put(user_id)
    waiting_events[user_id] = asyncio.Event()
    asyncio.create_task(match_partner(context, user_id))
    await update.message.reply_text("🔍 Поиск собеседника...", reply_markup=keyboard_searching())

async def match_partner(context, user_id):
    async with get_lock(user_id):
        try:
            await asyncio.sleep(1)  # минимальная задержка
            user = await get_user(user_id)
            theme, sub = user["theme"], user["sub"]

            candidates = []
            for uid in list(waiting_queue._queue):
                if uid == user_id:
                    continue
                other = await get_user(uid)
                if other["theme"] == theme and other["sub"] == sub:
                    candidates.append(uid)

            if candidates:
                partner_id = candidates[0]
                await clear_from_queue(user_id)
                await clear_from_queue(partner_id)

                active_chats[user_id] = partner_id
                active_chats[partner_id] = user_id

                await update_user_state(user_id, State.CHATTING)
                await update_user_state(partner_id, State.CHATTING)

                await context.bot.send_message(user_id, "✅ Партнёр найден!", reply_markup=keyboard_chat())
                await context.bot.send_message(partner_id, "✅ Партнёр найден!", reply_markup=keyboard_chat())

                waiting_events[user_id].set()
                waiting_events[partner_id].set()
                return

            await asyncio.wait_for(waiting_events[user_id].wait(), timeout=60)
        except asyncio.TimeoutError:
            await clear_from_queue(user_id)
            await update_user_state(user_id, State.MENU)
            await context.bot.send_message(user_id, "Сейчас все заняты. Попробуйте позже.", reply_markup=keyboard_main())
        finally:
            waiting_events.pop(user_id, None)

async def clear_from_queue(uid):
    temp_q = asyncio.Queue()
    while not waiting_queue.empty():
        item = await waiting_queue.get()
        if item != uid:
            await temp_q.put(item)
    while not temp_q.empty():
        await waiting_queue.put(await temp_q.get())

async def cancel_search(update, context, user_id):
    await clear_from_queue(user_id)
    await update_user_state(user_id, State.MENU)
    await update.message.reply_text("⛔ Поиск отменён.", reply_markup=keyboard_main())

async def finish_dialog(update, context, user_id):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        await update_user_state(partner_id, State.MENU)
        await context.bot.send_message(partner_id, "❌ Диалог завершён партнёром.", reply_markup=keyboard_main())
    await update_user_state(user_id, State.MENU)
    await update.message.reply_text("Диалог завершён.", reply_markup=keyboard_main())

# --- Webhook ---
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return web.Response(status=500, text="error")

# --- Startup ---
async def on_startup(app):
    await init_db()
    await application.initialize()
    await application.start()
    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app):
    await application.stop()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    web.run_app(app, port=PORT)
