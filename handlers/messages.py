import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.keyboards import kb_after_sub, kb_searching, kb_chat
from core.i18n import tr
from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_sub, update_user_state
)
from core.topics import TOPICS
from core.matchmaking import add_to_queue, is_in_chat, remove_from_queue
from core.chat_control import end_dialog

logger = logging.getLogger(__name__)

async def get_topic_keyboard(user):
    topic_translated = [await tr(user, t) for t in TOPICS.keys()]
    return ReplyKeyboardMarkup([[t] for t in topic_translated], resize_keyboard=True)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("💬 MSG: %s", update.message.text)
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = await get_user(user_id)
    if not user:
        await update.message.reply_text(
            tr_lang("ru", "pls_start"),
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return

    state = user["state"]
    logger.debug("STATE=%s TEXT=%s", state, text)

    # ---------- Кнопка «Начать» ----------
    if text == await tr(user, "btn_start"):
        await update_user_state(user_id, "theme")
        user = await get_user(user_id)
        await update.message.reply_text(
            await tr(user, "pick_theme"),
            reply_markup=await get_topic_keyboard(user)
        )
        return

    # ---------- ШАГ 1: Никнейм ----------
    if state == "nickname":
        await update_user_nickname(user_id, text)
        await update_user_state(user_id, "gender")
        await update.message.reply_text(
            await tr(user, "choose_gender"),
            reply_markup=ReplyKeyboardMarkup(
                [[await tr(user, "gender_male")],
                 [await tr(user, "gender_female")],
                 [await tr(user, "gender_any")]],
                resize_keyboard=True
            )
        )
        return

    # ---------- ШАГ 2: Пол ----------
    elif state == "gender":
        valid_genders = [await tr(user, "gender_male"), await tr(user, "gender_female"), await tr(user, "gender_any")]
        if text not in valid_genders:
            await update.message.reply_text(
                await tr(user, "wrong_gender"),
                reply_markup=ReplyKeyboardMarkup([[g] for g in valid_genders], resize_keyboard=True)
            )
            return

        await update_user_gender(user_id, text)
        await update_user_state(user_id, "theme")
        
        user = await get_user(user_id)
        
        await update.message.reply_text(
            await tr(user, "pick_theme"),
            reply_markup=await get_topic_keyboard(user)
        )
        return

    # ---------- ШАГ 3: Тема ----------
    # ---------- ШАГ 3: Тема ----------
    if state == "theme":
        # Сопоставляем перевод обратно в ключ
        theme_key = None
        for key in TOPICS:
            if text == await tr(user, key) or text == key:
                theme_key = key
                break

        if not theme_key:
            await update.message.reply_text(await tr(user, "wrong_theme"))
            return

        await update_user_theme(user_id, theme_key)
        await update_user_state(user_id, "sub")

        # Получаем список подтем (ключи) + ключ для "any_sub"
        subtopics = TOPICS[theme_key] + ["any_sub"]

        # Переводим подтемы для показа
        subtopics_translated = [await tr(user, s) for s in subtopics]

        keyboard = [[s] for s in subtopics_translated]
        await update.message.reply_text(
            await tr(user, "choose_sub"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 4: Подтема ----------
    elif state == "sub":
        theme = user.get("theme")
        valid_sub_keys = TOPICS.get(theme, []) + ["any_sub"]

        # Переводим подтемы для сравнения
        valid_subs = [await tr(user, s) for s in valid_sub_keys]

        if text not in valid_subs:
            await update.message.reply_text(await tr(user, "wrong_sub"))
            return

        # Нужно найти ключ подтемы по переводу, чтобы сохранить в БД
        sub_key = valid_sub_keys[valid_subs.index(text)]

        await update_user_sub(user_id, sub_key)
        await update_user_state(user_id, "menu")

        # Перевод темы и подтемы для подтверждения
        msg = (
            f"{await tr(user, 'confirm_theme', theme=await tr(user, theme))}\n"
            f"{await tr(user, 'confirm_sub', sub=await tr(user, sub_key))}"
        )
        await update.message.reply_text(
            msg,
            reply_markup=await kb_after_sub(user)
        )
        return

    # ---------- Меню ----------
    elif state == "menu":
        if text == await tr(user, "btn_search"):
            await update_user_state(user_id, "searching")
            await update.message.reply_text(
                await tr(user, "searching"),
                reply_markup=await kb_searching(user)
            )
            await add_to_queue(user_id, user["theme"], user["sub"], context)
            return

        elif text == await tr(user, "btn_change_sub"):
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + [await tr(user, "any_sub")]
            await update.message.reply_text(
                await tr(user, "choose_sub"),
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        elif text == await tr(user, "btn_main_menu"):
            await update_user_state(user_id, "theme")
            user = await get_user(user_id)
            await update.message.reply_text(
                await tr(user, "pick_theme"),
                reply_markup=await get_topic_keyboard(user)
            )
            return

    # ---------- Поиск ----------
    elif state == "searching":
        if text == await tr(user, "btn_stop"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "menu")
            await update.message.reply_text(
                await tr(user, "search_stopped"),
                reply_markup=await kb_after_sub(user)
            )
            return

        elif text == await tr(user, "btn_change_sub"):
            await update_user_state(user_id, "sub")

            # Переводим ключи подтем
            sub_keys = TOPICS[user["theme"]] + ["any_sub"]
            subtopics = [await tr(user, s) for s in sub_keys]

            await update.message.reply_text(
                await tr(user, "choose_sub"),
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        elif text == await tr(user, "btn_main_menu"):
            await update_user_state(user_id, "theme")
            user = await get_user(user_id)

            # Перевод тем
            topic_keys = list(TOPICS.keys())
            topic_translated = [await tr(user, key) for key in topic_keys]

            await update.message.reply_text(
                await tr(user, "pick_theme"),
                reply_markup=await get_topic_keyboard(user)
            )
            return

        elif text == await tr(user, "btn_support"):
            await update.message.reply_text(
                await tr(user, "support_thanks"),
                reply_markup=await kb_searching(user)
            )
            return

        await update.message.reply_text(await tr(user, "default_searching"))
        return

    # ---------- Чат ----------
    elif await is_in_chat(user_id):
        if text == await tr(user, "btn_end"):
            await end_dialog(user_id, context)
            return

        elif text == await tr(user, "btn_new_partner"):
            await end_dialog(user_id, context, silent=True)
            await update_user_state(user_id, "menu")
            await update.message.reply_text(
                await tr(user, "main_menu"),
                reply_markup=await kb_after_sub(user)
            )
            return

        companion_id = user.get("companion_id")
        if companion_id:
            await context.bot.send_message(companion_id, text=text)
        return

    # ---------- Фолбэк ----------
    await update.message.reply_text(await tr(user, "error_fallback"))
