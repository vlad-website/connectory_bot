import logging
import os
import json
import asyncio
from aiohttp import web
from db import init_db, get_user, create_user, update_user_state, update_user_nickname, update_user_gender, update_user_theme, update_user_subcategory
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

ADMIN_ID = 491000185

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

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


def keyboard_main_menu():
    return ReplyKeyboardMarkup([["🔍 Найти собеседника"], ["❌ Завершить диалог"], ["🏠 Главное меню"]], resize_keyboard=True)


def keyboard_subcategories(theme):
    return ReplyKeyboardMarkup([[sub] for sub in topics[theme]] + [["🏠 Главное меню"]], resize_keyboard=True)


def keyboard_searching():
    return ReplyKeyboardMarkup([["Продлить поиск"], ["Выбрать другого партнёра"], ["⛔ Отменить поиск"], ["🏠 Главное меню"]], resize_keyboard=True)


def keyboard_dialog():
    return ReplyKeyboardMarkup([["Найти нового собеседника"], ["❌ Завершить диалог"]], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if user:
        nickname = user.get("nickname") or "друг"
        await update.message.reply_text(
            f"👋 С возвращением, {nickname}!",
            reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True)
        )
    else:
        await create_user(user_id)
        await update_user_state(user_id, STATE_NICKNAME)
        await update.message.reply_text(
            "👋 Привет! Я бот для знакомств и общения по интересам.\n"
            "Находи собеседников только на интересующие тебя темы!\n"
            "Введи свой ник (имя, по которому тебя увидит собеседник):"
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = await get_user(user_id)

    if not user:
        await create_user(user_id)
        await update_user_state(user_id, STATE_NICKNAME)
        await update.message.reply_text("👋 Привет! Введи свой ник:")
        return

    state = user.get("state", "")

    logger.info(f"User {user_id} state: {state}, message: {text}")

    if state == STATE_NICKNAME:
        await update_user_nickname(user_id, text[:32])
        await update_user_state(user_id, STATE_GENDER)
        await update.message.reply_text(
            f"Спасибо, {text[:32]}! Теперь выбери свой пол:",
            reply_markup=ReplyKeyboardMarkup(
                [["Мужской"], ["Женский"], ["Не указывать"]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return

    if state == STATE_GENDER:
        if text not in ["Мужской", "Женский", "Не указывать"]:
            await update.message.reply_text("Пожалуйста, выбери пол из предложенных вариантов.")
            return

        await update_user_gender(user_id, text)
        await update_user_state(user_id, "choosing_theme")
        await update.message.reply_text(
            "✅ Готово! Теперь выбери тему для общения:",
            reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True)
        )
        return

    if text == "🏠 Главное меню":
        await update_user_state(user_id, "choosing_theme")
        await update.message.reply_text("Выберите тему:", reply_markup=ReplyKeyboardMarkup([[k] for k in topics], resize_keyboard=True))
        return

    if state == "choosing_theme" and text in topics:
        await update_user_theme(user_id, text)
        await update_user_state(user_id, "choosing_sub")
        await update.message.reply_text("Выберите подкатегорию:", reply_markup=keyboard_subcategories(text))
        return

    if state == "choosing_sub":
        theme = user.get("theme")
        if theme is None:
            await update.message.reply_text("Сначала выберите тему.")
            await update_user_state(user_id, "choosing_theme")
            return

        if text in topics.get(theme, []):
            await update_user_subcategory(user_id, text)
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


async def start_searching(update, context, user_id):
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("Пользователь не найден.")
        return

    if user.get("state") in ["searching", "chatting"]:
        await update.message.reply_text("Вы уже ищете или в диалоге.")
        return

    theme = user.get("theme")
    sub = user.get("sub")

    if not theme or not sub:
        await update.message.reply_text("Сначала выберите тему и подкатегорию.")
        return

    await update_user_state(user_id, "searching")
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
        user = await get_user(user_id)
        if user and user.get("state") == "searching":
            await update_user_state(user_id, "menu")
            await context.bot.send_message(user_id, "Сейчас все заняты. Попробуйте позже.", reply_markup=keyboard_main_menu())
    finally:
        waiting_events.pop(user_id, None)


async def try_match_partner(user_id, context):
    user = await get_user(user_id)
    if not user or user.get("state") != "searching":
        return

    theme, sub = user["theme"], user["sub"]
    temp = []
    partner = None

    for _ in range(waiting_queue.qsize()):
        other = await waiting_queue.get()
        if other == user_id:
            temp.append(other)
            continue

        other_user = await get_user(other)
        if other_user and other_user.get("theme") == theme:
            sub1, sub2 = other_user.get("sub"), sub
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
        await update_user_state(uid, "chatting")

    active_chats[user1] = user2
    active_chats[user2] = user1

    user1_data = await get_user(user1)
    user2_data = await get_user(user2)

    theme = user1_data.get("theme")
    sub1 = user1_data.get("sub")
    sub2 = user2_data.get("sub")

    sub_display = sub2 if sub1 == "Любая подкатегория" else sub1 if sub2 == "Любая подкатегория" else sub1

    for uid in (user1, user2):
        await bot.send_message(uid, f"Вы подключены. Тема: {theme}\nПодкатегория: {sub_display}", reply_markup=keyboard_dialog())

    for uid in (user1, user2):
        if uid in waiting_events:
            waiting_events[uid].set()


async def cancel_search(update, context, user_id):
    user = await get_user(user_id)
    if not user or user.get("state") != "searching":
        await update.message.reply_text("Вы не в поиске.")
        return

    await update_user_state(user_id, "menu")
    await remove_from_queue(user_id)
    if user_id in waiting_events:
        waiting_events[user_id].set()
    await update.message.reply_text("Поиск отменён.", reply_markup=keyboard_main_menu())


async def end_dialog(update, context, user_id):
    user = await get_user(user_id)
    if not user or user.get("state") != "chatting":
        await update.message.reply_text("Вы не в диалоге.")
        return

    partner = active_chats.pop(user_id, None)
    await update_user_state(user_id, "menu")

    if partner:
        active_chats.pop(partner, None)
        await update_user_state(partner, "menu")
        await context.bot.send_message(partner, "Собеседник завершил диалог.", reply_markup=keyboard_main_menu())

    await update.message.reply_text("Диалог завершён.", reply_markup=keyboard_main_menu())


async def remove_from_queue(user_id):
    # Очистка из очереди ожидания (непросто, поэтому тут только фильтрация)
    temp = []
    while not waiting_queue.empty():
        uid = await waiting_queue.get()
        if uid != user_id:
            temp.append(uid)
    for uid in temp:
        await waiting_queue.put(uid)


def increment_stats(theme, subcategory):
    # Заглушка: здесь можешь увеличить счетчики в БД или файле
    pass


async def health(request):
    return web.Response(text="ok")


async def handle_webhook(request):
    body = await request.text()
    update = Update.de_json(json.loads(body), application.bot)
    await application.update_queue.put(update)
    return web.Response()


def main():
    asyncio.run(init_db())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    app = web.Application()
    app.router.add_post(f"/{os.getenv('BOT_TOKEN')}", handle_webhook)
    app.router.add_get("/health", health)
    web.run_app(app, port=int(os.getenv("PORT", 8080)))


if __name__ == "__main__":
    main()
