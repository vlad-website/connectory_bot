# handlers/messages.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.keyboards import kb_after_sub, kb_searching, kb_chat

import logging

from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_sub, update_user_state
)
from core.topics import TOPICS
from core.matchmaking import add_to_queue, is_in_chat, remove_from_queue
from core.chat_control import end_dialog

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("💬 MSG: %s", update.message.text)
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, отправьте /start.")
        return

    state = user["state"]
    logger.debug("STATE=%s TEXT=%s", state, text)

    # ---------- ШАГ 1: Никнейм ----------
    if state == "nickname":
        # 1. сохраняем ник
        await update_user_nickname(user_id, text)

        # 2. проверяем, что ник действительно записан
        user_after = await get_user(user_id)
        logger.debug("After nickname update: %s", user_after)

        # 3. переводим пользователя к выбору пола
        await update_user_state(user_id, "gender")

        await update.message.reply_text(
            "Укажи свой пол:",
            reply_markup=ReplyKeyboardMarkup(
                [["Мужской"], ["Женский"], ["Не важно"]], resize_keyboard=True
            )
        )
        return                      # <– обязателен, чтобы не провалиться дальше

    # ---------- ШАГ 2: Пол ----------
    elif state == "gender":
        if text not in ("Мужской", "Женский", "Не важно"):
            await update.message.reply_text(
                "Пожалуйста, выбери пол:", 
                reply_markup=ReplyKeyboardMarkup(
                    [["Мужской"], ["Женский"], ["Не важно"]], resize_keyboard=True
                )
            )
            return

        gender = text            # уже нормальная форма
        await update_user_gender(user_id, gender)
        await update_user_state(user_id, "theme")

        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(
            "Выбери интересующую тебя тему:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 3: Тема ----------
    elif state == "theme":
        if text not in TOPICS:
            await update.message.reply_text("Пожалуйста, выбери тему из списка.")
            return

        await update_user_theme(user_id, text)
        await update_user_state(user_id, "sub")

        subtopics = TOPICS[text] + ["Любая подтема"]
        keyboard = [[s] for s in subtopics]
        await update.message.reply_text(
            "Теперь выбери подтему:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 4: Подтема ----------
    elif state == "sub":
        theme = user["theme"]
        valid_subs = TOPICS.get(theme, []) + ["Любая подтема"]
        if text not in valid_subs:
            await update.message.reply_text("Выбери подтему из списка.")
            return

        await update_user_sub(user_id, text)
        await update_user_state(user_id, "menu")           # ← теперь 'menu'
        await update.message.reply_text(
            f"Вы выбрали: {theme} / {text}",
            reply_markup=kb_after_sub()                    # ← меню после выбора
        )
        return

    # ---------- Новый блок ----------
    elif state == "menu":
        if text == "🔍 Начать поиск":
            await update_user_state(user_id, "searching")
            await update.message.reply_text("🔎 Ищу собеседника...", reply_markup=kb_searching())
            await add_to_queue(user_id, user["theme"], user["sub"])
            return

        if text == "Изменить подтему":
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + ["Любая подтема"]
            await update.message.reply_text(
                "Выберите подтему:",
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        if text == "🏠 Главное меню":
            await update_user_state(user_id, "theme")
            keyboard = [[t] for t in TOPICS.keys()]
            await update.message.reply_text(
                "Выбери интересующую тему:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

    # ---------- Поиск ----------
    elif state == "searching":
        if text == "⛔ Остановить поиск":
            # 1) убираем из очереди
            await remove_from_queue(user_id)
            # 2) возвращаем в меню (можно начать поиск заново)
            await update_user_state(user_id, "menu")
            await update.message.reply_text(
                "Поиск остановлен.",
                reply_markup=kb_after_sub()           # та же клавиатура, что после выбора подтемы
            )
            return

        if text == "Изменить подтему":
            await remove_from_queue(user_id)
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + ["Любая подтема"]
            await update.message.reply_text(
                "Выберите новую подтему:",
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        if text == "🏠 Главное меню":
            await remove_from_queue(user_id)
            await update_user_state(user_id, "theme")
            keyboard = [[t] for t in TOPICS.keys()]
            await update.message.reply_text(
                "Выбери тему:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        if text == "❤️ Поддержать проект":
            await update.message.reply_text(
                "🙏 Спасибо за поддержку!\n(Здесь будет ссылка на донат)",
                reply_markup=kb_searching()
            )
            return

        # дефолт: ничто из меню не нажато
        await update.message.reply_text("⏳ Ищем собеседника...")
        return

    # ---------- Фолбэк ----------
    await update.message.reply_text("❌ Что-то пошло не так. Напиши /start.")
