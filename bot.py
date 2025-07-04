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

# Ваш Telegram user_id (замени на свой)
ADMIN_ID = 491000185

# Настройка логгирования в файл bot.log
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

# Добавляем кнопку "Любая подкатегория" в конец каждой темы
for theme in topics:
    if "Любая подкатегория" not in topics[theme]:
        topics[theme].append("Любая подкатегория")

# ---------- Функции клавиатур ----------

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

# ---------- Обработка команд и сообщений ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    users[user_id] = {"state": "choosing_theme"}
    logger.info(f"User {user_id} started bot.")
    description = (
        "Привет! Этот бот поможет найти собеседника для общения по интересующим темам.\n\n"
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

    # Главное меню из любого состояния
    if text == "🏠 Главное меню":
        users[user_id]["state"] = "choosing_theme"
        keyboard = [[key] for key in topics.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вы вернулись в главное меню. Выберите тему:", reply_markup=reply_markup)
        return

    # Выбор темы
    if state == "choosing_theme" and text in topics:
        users[user_id]["theme"] = text
        users[user_id]["state"] = "choosing_sub"
        await update.message.reply_text("Теперь выбери подкатегорию:", reply_markup=subcategories_keyboard(text))
        return

    # Выбор подкатегории
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

    # Главное меню — действия
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

    # Во время диалога
    if state == "chatting":
        if text == "Найти нового собеседника":
            await start_searching(update, context, user_id)
            return
        elif text == "❌ Завершить диалог":
            await end_dialog(update, context, user_id)
            return
        else:
            # Пересылаем сообщения собеседнику
            partner_id = active_chats.get(user_id)
            if partner_id:
                await context.bot.send_message(chat_id=partner_id, text=text)
            return

    # Если ничего не подошло
    await update.message.reply_text("Пожалуйста, выбери тему или нажми «🏠 Главное меню».")

# ---------- Логика поиска собеседника ----------

async def start_searching(update, context, user_id):
    # Проверим, если пользователь уже в поиске или в чате
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
    logger.info(f"User {user_id} начал поиск по теме '{theme}' и подкатегории '{sub}'")
    await update.message.reply_text("Поиск собеседника...")

    # Попытка найти партнёра
    partner_id = find_partner(user_id)
    if partner_id:
        await start_chat(update, context, user_id, partner_id)
        return

    # Таймер ожидания 60 секунд
    try:
        await asyncio.wait_for(wait_for_partner(user_id), timeout=60)
    except asyncio.TimeoutError:
        # Время вышло — предложение действий
        if users[user_id]["state"] == "searching":
            await update.message.reply_text(
                "Сейчас все собеседники заняты, не удалось найти свободного партнёра.",
                reply_markup=searching_options_keyboard(),
            )

async def wait_for_partner(user_id):
    # Просто ждём, пока пользователя не уберут из waiting_users (вызов find_partner у другого пользователя)
    while user_id in waiting_users:
        await asyncio.sleep(1)

def find_partner(user_id):
    # Поиск подходящего партнёра из waiting_users по теме и подкатегории
    theme = users[user_id].get("theme")
    sub = users[user_id].get("sub")

    for other_id in waiting_users:
        if other_id == user_id:
            continue
        other_theme = users[other_id].get("theme")
        other_sub = users[other_id].get("sub")
        # Условие совпадения темы и подкатегории с учётом "Любая подкатегория"
        theme_match = theme == other_theme
        if not theme_match:
            continue
        # Если кто-то выбрал "Любая подкатегория", считаем что подходит
        if sub == "Любая подкатегория" or other_sub == "Любая подкатегория" or sub == other_sub:
            # Удаляем обоих из очереди ожидания
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

    # Формируем сообщение с темой и подкатегорией
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

    await context.bot.send_message(chat_id=user_id, text=msg_user, reply_markup=dialog_keyboard())
    await context.bot.send_message(chat_id=partner_id, text=msg_partner, reply_markup=dialog_keyboard())

    logger.info(f"User {user_id} и User {partner_id} начали чат по теме '{theme}' и подкатегории '{sub_display}'")

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
        logger.info(f"User {user_id} завершил диалог")
    elif state == "searching":
        if user_id in waiting_users:
            waiting_users.remove(user_id)
        users[user_id]["state"] = "menu"
        await update.message.reply_text("Поиск прерван.", reply_markup=main_menu_keyboard())
        logger.info(f"User {user_id} прервал поиск")
    else:
        await update.message.reply_text("Вы не в диалоге.")

# ---------- Статистика ----------

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

# ---------- Запуск бота ----------

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
