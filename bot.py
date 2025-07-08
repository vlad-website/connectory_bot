import os
import logging
import asyncio
import json
from aiohttp import web

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db import init_db, get_user, create_user, update_user_state, update_user_nickname, update_user_gender

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Состояния анкеты ---
STATE_NICKNAME = "nickname"
STATE_GENDER = "gender"

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

# Хранение состояния в памяти (в идеале заменить на БД)
users = {}

# --- Клавиатуры ---
def keyboard_main_menu():
    return ReplyKeyboardMarkup([["🔍 Найти собеседника"], ["❌ Завершить диалог"], ["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_subcategories(theme):
    return ReplyKeyboardMarkup([[sub] for sub in topics[theme]] + [["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_searching():
    return ReplyKeyboardMarkup([["Продлить поиск"], ["Выбрать другого партнёра"], ["⛔ Отменить поиск"], ["🏠 Главное меню"]], resize_keyboard=True)

def keyboard_dialog():
    return ReplyKeyboardMarkup([["Найти нового собеседника"], ["❌ Завершить диалог"]], resize_keyboard=True)

# --- Хендлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if user:
        users[user_id] = dict(user)  # синхронизируем с памятью
        nickname = user.get("nickname") or "друг"
        await update.message.reply_text(
            f"👋 С возвращением, {nickname}!",
            reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True)
        )
    else:
        await create_user(user_id)
        await update_user_state(user_id, STATE_NICKNAME)
        users[user_id] = {"state": STATE_NICKNAME}
        await update.message.reply_text(
            "👋 Привет! Я бот для знакомств и общения по интересам.\n"
            "Введи свой ник (имя, по которому тебя увидит собеседник):"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = users.get(user_id)
    if not user:
        user_db = await get_user(user_id)
        if user_db:
            users[user_id] = dict(user_db)
            user = users[user_id]
        else:
            await create_user(user_id)
            await update_user_state(user_id, STATE_NICKNAME)
            users[user_id] = {"state": STATE_NICKNAME}
            await update.message.reply_text("👋 Привет! Введи свой ник:")
            return

    state = user.get("state", "")
    logger.info(f"User {user_id} state: {state}, message: {text}")

    # Анкета: никнейм
    if state == STATE_NICKNAME:
        await update_user_nickname(user_id, text[:32])
        await update_user_state(user_id, STATE_GENDER)
        user["state"] = STATE_GENDER
        await update.message.reply_text(
            f"Спасибо, {text[:32]}! Теперь выбери свой пол:",
            reply_markup=ReplyKeyboardMarkup(
                [["Мужской"], ["Женский"], ["Не указывать"]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return

    # Анкета: пол
    if state == STATE_GENDER:
        if text not in ["Мужской", "Женский", "Не указывать"]:
            await update.message.reply_text("Пожалуйста, выбери пол из предложенных вариантов.")
            return
        await update_user_gender(user_id, text)
        await update_user_state(user_id, "choosing_theme")
        user["state"] = "choosing_theme"
        await update.message.reply_text(
            "✅ Готово! Теперь выбери тему для общения:",
            reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True)
        )
        return

    if text == "🏠 Главное меню":
        await update_user_state(user_id, "choosing_theme")
        user["state"] = "choosing_theme"
        await update.message.reply_text("Выберите тему:", reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))
        return

    if state == "choosing_theme" and text in topics:
        user["theme"] = text
        user["state"] = "choosing_sub"
        await update_user_state(user_id, "choosing_sub")
        await update.message.reply_text("Выберите подкатегорию:", reply_markup=keyboard_subcategories(text))
        return

    if state == "choosing_sub":
        theme = user.get("theme")
        if text in topics.get(theme, []):
            user["sub"] = text
            user["state"] = "menu"
            await update_user_state(user_id, "menu")
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

# --- Поиск собеседника ---
async def start_searching(update, context, user_id):
    user = users.get(user_id)
    if not user:
        await update.message.reply_text("Ошибка, пользователь не найден.")
        return

    if user.get("state") in ["searching", "chatting"]:
        await update.message.reply_text("Вы уже ищете или в диалоге.")
        return

    theme = user.get("theme")
    sub = user.get("sub")

    if not theme or not sub:
        await update.message.reply_text("Сначала выберите тему и подкатегорию.")
        return

    user["state"] = "searching"
    await update_user_state(user_id, "searching")
    await waiting_queue.put(user_id)

    asyncio.create_task(search_partner_background(context, user_id))
    await update.message.reply_text("Поиск собеседника...", reply_markup=keyboard_searching())

async def search_partner_background(context, user_id):
    waiting_events[user_id] = asyncio.Event()
    await try_match_partner(user_id, context)

    try:
        await asyncio.wait_for(waiting_events[user_id].wait(), timeout=60)
    except asyncio.TimeoutError:
        await remove_from_queue(user_id)
        user = users.get(user_id)
        if user and user.get("state") == "searching":
            user["state"] = "menu"
            await update_user_state(user_id, "menu")
            await context.bot.send_message(user_id, "Сейчас все заняты. Попробуйте позже.", reply_markup=keyboard_main_menu())
    finally:
        waiting_events.pop(user_id, None)

async def try_match_partner(user_id, context):
    user = users.get(user_id)
    if not user or user.get("state") != "searching":
        return

    theme, sub = user.get("theme"), user.get("sub")

    # Пытаемся найти пару
    candidates = []
    for candidate_id in list(waiting_queue._queue):
        if candidate_id == user_id:
            continue
        c_user = users.get(candidate_id)
        if not c_user or c_user.get("state") != "searching":
            continue
        if c_user.get("theme") == theme and c_user.get("sub") == sub:
            candidates.append(candidate_id)

    if candidates:
        partner_id = candidates[0]
        await remove_from_queue(user_id)
        await remove_from_queue(partner_id)

        # Устанавливаем чат
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id

        users[user_id]["state"] = "chatting"
        users[partner_id]["state"] = "chatting"

        await update_user_state(user_id, "chatting")
        await update_user_state(partner_id, "chatting")

        await context.bot.send_message(user_id, "✅ Партнёр найден! Начинайте общение.\nЧтобы закончить диалог — нажмите ❌ Завершить диалог.", reply_markup=keyboard_dialog())
        await context.bot.send_message(partner_id, "✅ Партнёр найден! Начинайте общение.\nЧтобы закончить диалог — нажмите ❌ Завершить диалог.", reply_markup=keyboard_dialog())

        # Сигналим ожидающему
        if waiting_events.get(user_id):
            waiting_events[user_id].set()
        if waiting_events.get(partner_id):
            waiting_events[partner_id].set()

async def remove_from_queue(user_id):
    try:
        # Очистка из очереди
        new_queue = asyncio.Queue()
        while not waiting_queue.empty():
            uid = await waiting_queue.get()
            if uid != user_id:
                await new_queue.put(uid)
        while not new_queue.empty():
            uid = await new_queue.get()
            await waiting_queue.put(uid)
    except Exception as e:
        logger.error(f"Ошибка при удалении из очереди {user_id}: {e}")

async def cancel_search(update, context, user_id):
    await remove_from_queue(user_id)
    user = users.get(user_id)
    if user:
        user["state"] = "menu"
        await update_user_state(user_id, "menu")
    await update.message.reply_text("Поиск отменён.", reply_markup=keyboard_main_menu())

async def end_dialog(update, context, user_id):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        partner = users.get(partner_id)
        if partner:
            partner["state"] = "menu"
            await update_user_state(partner_id, "menu")
            await context.bot.send_message(partner_id, "Диалог завершён партнёром.", reply_markup=keyboard_main_menu())
    user = users.get(user_id)
    if user:
        user["state"] = "menu"
        await update_user_state(user_id, "menu")
    await update.message.reply_text("Диалог завершён.", reply_markup=keyboard_main_menu())

# --- Статистика (простейшая) ---
stats = {}

def increment_stats(theme, sub):
    key = f"{theme} / {sub}"
    stats[key] = stats.get(key, 0) + 1

# --- Обработчик вебхука ---
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return web.Response(status=500, text="error")

# --- Запуск ---
async def on_startup(app):
    await application.initialize()
    await init_db()
    await application.start()

    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        logger.error("WEBHOOK_URL не задан в окружении")

async def on_cleanup(app):
    await application.stop()

# Добавляем хендлеры
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

# aiohttp сервер
app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    web.run_app(app, port=PORT)
