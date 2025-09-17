import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.keyboards import kb_after_sub, kb_searching, kb_main_menu
from core.i18n import tr
from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_sub, update_user_state,
    increment_messages
)
from core.topics import TOPICS
from core.matchmaking import add_to_queue, remove_from_queue, active_search_tasks, is_in_chat
from core.chat_control import end_dialog
from handlers.admin import send_admin_stats
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message is None:
            logger.debug("Received update without message, ignoring.")
            return

        user_id = update.effective_user.id
        text = (update.message.text or "").strip()

        # --- Игнорируем команды и сообщения с entity bot_command ---
        if text.startswith("/"):
            logger.debug("Ignoring command-like text in message_handler: %s", text)
            return
        entities = update.message.entities or []
        for e in entities:
            if getattr(e, "type", None) == "bot_command":
                logger.debug("Ignoring message with bot_command entity: %s", text)
                return

        # Получаем пользователя (состояние хранится в БД)
        try:
            user = await get_user(user_id)
        except Exception:
            logger.exception("Failed to get user %s", user_id)
            await update.message.reply_text("❌ Ошибка базы. Попробуйте /start")
            return

        if not user:
            await update.message.reply_text("⚠️ Нажмите /start")
            return

        state = user.get("state")
        logger.debug("message_handler: user=%s state=%s text=%r lang=%s",
                     user_id, state, text, user.get("lang"))

        # --- Ранняя обработка STOP (как было) ---
        stop_label = await tr(user, "btn_stop")
        if text == stop_label:
            await handle_stop_search(user_id, user, context)
            return

        # --- Регистрация: nickname ---
        if state == "nickname":
            try:
                await update_user_nickname(user_id, text)
                await update_user_state(user_id, "gender")
                user = await get_user(user_id)
            except Exception:
                logger.exception("Failed to save nickname or state for user %s", user_id)
                await update.message.reply_text("❌ Ошибка базы. Попробуйте ещё раз или /start")
                return

            keyboard = ReplyKeyboardMarkup(
                [[await tr(user, "gender_male")],
                 [await tr(user, "gender_female")],
                 [await tr(user, "gender_any")]],
                resize_keyboard=True
            )
            await update.message.reply_text(await tr(user, "choose_gender"), reply_markup=keyboard)
            return

        # --- Регистрация: gender ---
        if state == "gender":
            if user.get("gender"):
                logger.debug("User %s already has gender=%s — переход в menu", user_id, user.get("gender"))
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                return

            valid_genders = [await tr(user, "gender_male"),
                             await tr(user, "gender_female"),
                             await tr(user, "gender_any")]
            if text not in valid_genders:
                await update.message.reply_text(await tr(user, "wrong_gender"),
                                                reply_markup=ReplyKeyboardMarkup([[g] for g in valid_genders],
                                                                               resize_keyboard=True))
                return

            try:
                await update_user_gender(user_id, text)
                await update_user_state(user_id, "menu")
                user = await get_user(user_id)
            except Exception:
                logger.exception("Failed to update gender/state for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить пол. Попробуйте ещё раз или /start")
                return

            await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
            return

        # --- Главное меню ---
        if state == "menu":
            start_btn = await tr(user, "btn_start_chat")
            stats_btn = await tr(user, "btn_stats")
            settings_btn = await tr(user, "btn_settings")
            suggest_btn = await tr(user, "btn_suggest")
            vip_btn = await tr(user, "btn_get_vip")
            donate_btn = await tr(user, "btn_donate")

            menu_actions = {
                start_btn: "theme",
                stats_btn: "stats",
                settings_btn: "settings",
                suggest_btn: "suggest",
                vip_btn: "vip",
                donate_btn: "donate",
            }

            if text in menu_actions:
                action = menu_actions[text]

                if action == "theme":
                    try:
                        await update_user_state(user_id, "theme")
                        user = await get_user(user_id)
                        await update.message.reply_text(
                            await tr(user, "pick_theme"),
                            reply_markup=await get_topic_keyboard(user)
                        )
                    except Exception:
                        logger.exception("Failed to set state=theme for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return

                elif action == "stats":
                    await update.message.reply_text(await tr(user, "stats_in_progress"))
                    return

                elif action == "settings":
                    await update.message.reply_text(await tr(user, "settings_in_progress"))
                    return

                elif action == "suggest":
                    try:
                        await update_user_state(user_id, "suggest")
                        user = await get_user(user_id)
                        await update.message.reply_text(await tr(user, "pls_suggest"))
                    except Exception:
                        logger.exception("Failed to set state=suggest for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return

                elif action == "vip":
                    await update.message.reply_text(await tr(user, "vip_soon"))
                    return

                elif action == "donate":
                    await update.message.reply_text(await tr(user, "donate_thanks"))
                    return

            if text == "📊 Админ статистика":
                if user_id in ADMIN_IDS:
                    await send_admin_stats(update, context)
                else:
                    await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
                return

        # --- Дальше аналогично: theme, sub, menu_after_sub, searching, chat, suggest ---
        # во всех ветках:
        # 1) DB update в try/except
        # 2) user = await get_user(user_id) сразу после update
        # 3) использование tr(user, ...) и клавиатур с актуальным user

        # --- Фолбэк ---
        await update.message.reply_text(await tr(user, "error_fallback"))

    except Exception:
        logger.exception("Unhandled exception in message_handler")
        try:
            await update.message.reply_text("Произошла ошибка — попробуйте /start или сообщите администратору.")
        except Exception:
            logger.exception("Also failed to notify user after handler exception")
