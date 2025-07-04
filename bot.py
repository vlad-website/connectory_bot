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

# ---------- Настройки и переменные ----------

ADMIN_ID = 491000185

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
)
logger = logging.getLogger(__name__)

users = {}
waiting_queue = asyncio.Queue()  # Очередь ожидания
active_chats = {}
waiting_events = {}  # user_id -> asyncio.Event()

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

# ---------- Клавиатуры ----------

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
        [["Продлить поиск"], ["Выбрать другого партнёра"], ["⛔ Отменить поиск"], ["🏠 Главное меню"]],
        resize_keyboard=True,
    )

def dialog_keyboard():
    return ReplyKeyboardMarkup(
        [["Найти нового собеседника"], ["❌ Завершить диалог"]],
        resize_keyboard=True,
    )

# ---------- Обработчики ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    logger.info(f"User {user_id} started bot.")
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

    logger.info(f"User {user_id} sent message: {text}")

    if text == "🏠 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
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
            logger.info(f"User {user_id} выбрал тему '{theme}' и подкатегорию '{text}'")
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

    if state == "searching":
        # Обработка кнопки отмены поиска
        if text == "⛔ Отменить поиск":
            await cancel_search(update, context, user_id)
            return
        elif text == "Продлить поиск":
            await update.message.reply_text("Продлеваю поиск...")
            # Просто сбрасываем таймаут ожидания, запустив заново поиск
            # Для упрощения: не делаем здесь, поиск уже идёт в фоне
            return
        elif text == "Выбрать другого партнёра":
            await cancel_search(update, context, user_id)
            await start_searching(update, context, user_id)
            return
        else:
            await update.message.reply_text("Вы сейчас в поиске, дождитесь партнёра или отмените поиск.")
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

# ---------- Поиск собеседника ----------

async def start_searching(update, context, user_id):
    state = users[user_id].get("state")
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
    waiting_events[user_id] = asyncio.Event()
    await waiting_queue.put(user_id)
    logger.info(f"User {user_id} начал поиск по теме '{theme}' и подкатегории '{sub}'")

    await update.message.reply_text("Поиск собеседника...", reply_markup=searching_options_keyboard())

    # Попытка найти партнёра из очереди
    await try_match_partner(user_id, context)

    try:
        # Ждём либо партнёра, либо отмены, с таймаутом 60 секунд
        await asyncio.wait_for(waiting_events[user_id].wait(), timeout=60)
    except asyncio.TimeoutError:
        if users[user_id].get("state") == "searching":
            await update.message.reply_text(
                "Сейчас все собеседники заняты, не удалось найти свободного партнёра.",
                reply_markup=searching_options_keyboard(),
            )
            # Удаляем из очереди ожидания, если ещё там
            await remove_from_queue(user_id)
            users[user_id]["state"] = "menu"
    finally:
        waiting_events.pop(user_id, None)

async def try_match_partner(user_id, context):
    """Пытаемся найти подходящего партнёра для user_id из очереди"""
    if users[user_id].get("state") != "searching":
        return

    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    # Проходим по очереди, пытаемся найти подходящего
    qsize = waiting_queue.qsize()
    temp_users = []
    partner_id = None

    for _ in range(qsize):
        other_id = await waiting_queue.get()
        if other_id == user_id:
            temp_users.append(other_id)
            continue

        other_theme = users.get(other_id, {}).get("theme")
        other_sub = users.get(other_id, {}).get("sub")

        if not other_theme or not other_sub:
            # Если данные некорректны — пропускаем
            temp_users.append(other_id)
            continue

        if other_theme == theme and (sub == "Любая подкатегория" or other_sub == "Любая подкатегория" or sub == other_sub):
            partner_id = other_id
            break
        else:
            temp_users.append(other_id)

    # Возвращаем всех пользователей обратно в очередь, кроме найденного партнёра
    for u in temp_users:
        await waiting_queue.put(u)

    if partner_id:
        # Убираем user_id из очереди (если там)
        await remove_from_queue(user_id)

        # Начинаем чат
        await start_chat(context.bot, user_id, partner_id)

async def remove_from_queue(user_id):
    """Удаляет пользователя из очереди, если он там есть"""
    temp_users = []
    removed = False
    while not waiting_queue.empty():
        u = await waiting_queue.get()
        if u != user_id:
            temp_users.append(u)
        else:
            removed = True
    for u in temp_users:
        await waiting_queue.put(u)
    return removed

async def start_chat(bot, user_id, partner_id):
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

    msg_user = f"Вы подключены к собеседнику.\nТема: «{theme}»\nПодкатегория: «{sub_display}»"
    msg_partner = f"Вы подключены к собеседнику.\nТема: «{theme}»\nПодкатегория: «{sub_display}»"

    await bot.send_message(chat_id=user_id, text=msg_user, reply_markup=dialog_keyboard())
    await bot.send_message(chat_id=partner_id, text=msg_partner, reply_markup=dialog_keyboard())

    logger.info(f"User {user_id} и User {partner_id} начали чат по теме '{theme}' и подкатегории '{sub_display}'")

    # Сигнализируем об успешном подборе партнёра
    if user_id in waiting_events:
        waiting_events[user_id].set()
    if partner_id in waiting_events:
        waiting_events[partner_id].set()

async def cancel_search(update, context, user_id):
    if users[user_id].get("state") == "searching":
        users[user_id]["state"] = "menu"
        await remove_from_queue(user_id)
        if user_id in waiting_events:
            waiting_events[user_id].set()  # Прервать ожидание
        await update.message.reply_text("Поиск отменён.", reply_markup=main_menu_keyboard())
        logger.info(f"User {user_id} отменил поиск.")
    else:
        await update.message.reply_text("Вы не в поиске.")

async def end_dialog(update, context, user_id):
    state = users[user_id]["state"]
    if state == "chatting":
        partner_id = active_chats.get(user_id)
