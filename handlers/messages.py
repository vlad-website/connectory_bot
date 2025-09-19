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

        # --- Получаем пользователя ---
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

        # --- STOP ---
        stop_label = await tr(user, "btn_stop")
        if text == stop_label:
            try:
                await handle_stop_search(user_id, user, context)
            except Exception:
                logger.exception("Failed to handle stop_search for user %s", user_id)
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
            # действия по ключам
            menu_actions = {
                "btn_start_chat": "theme",
                "btn_stats": "stats",
                "btn_settings": "settings",
                "btn_suggest": "suggest",
                "btn_get_vip": "vip",
                "btn_donate": "donate",
            }
        
            # построим mapping: translated_label -> key
            translated_map = {}
            for key in menu_actions.keys():
                try:
                    label = (await tr(user, key)) or key
                except Exception:
                    logger.exception("tr() failed for menu key %s (user=%s)", key, user_id)
                    label = key
                translated_map[label.strip()] = key
        
            admin_label = "📊 Админ статистика"
            logger.debug("MENU: user=%s text=%r translated_map=%s", user_id, text, list(translated_map.keys()))
        
            # сначала — админская кнопка (она добавлена хардкодом в kb_main_menu)
            if text.strip() == admin_label:
                if user_id in ADMIN_IDS:
                    try:
                        await send_admin_stats(update, context)
                    except Exception:
                        logger.exception("Failed to send admin stats to user %s", user_id)
                else:
                    await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
                return
        
            # найдем ключ по переводу
            matched_key = translated_map.get(text.strip())
            if matched_key:
                action = menu_actions[matched_key]
                try:
                    if action == "theme":
                        await update_user_state(user_id, "theme")
                        user = await get_user(user_id)
                        try:
                            await update.message.reply_text(await tr(user, "pick_theme"), reply_markup=await get_topic_keyboard(user))
                        except Exception:
                            # если клавиатура/тема упали — логируем и даём понятное сообщение
                            logger.exception("Failed to send topic keyboard to user %s", user_id)
                            await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    elif action == "stats":
                        await update.message.reply_text(await tr(user, "stats_in_progress"))
                    elif action == "settings":
                        await update.message.reply_text(await tr(user, "settings_in_progress"))
                    elif action == "suggest":
                        await update_user_state(user_id, "suggest")
                        user = await get_user(user_id)
                        await update.message.reply_text(await tr(user, "pls_suggest"))
                    elif action == "vip":
                        await update.message.reply_text(await tr(user, "vip_soon"))
                    elif action == "donate":
                        await update.message.reply_text(await tr(user, "donate_thanks"))
                except Exception:
                    logger.exception("Menu action %s failed for user %s", action, user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                return
        
        # --- Тема ---
        if state == "theme":
            # кнопка назад
            if text.strip() == (await tr(user, "btn_main_menu")).strip():
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to return to menu from theme for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте /start.")
                return
        
            # Создаём mapping переведённого названия темы -> ключ темы
            topics_map = {}
            for key in TOPICS.keys():
                try:
                    label = (await tr(user, key)) or key
                except Exception:
                    logger.exception("tr() failed for topic key %s (user=%s)", key, user_id)
                    label = key
                topics_map[label.strip()] = key
        
            logger.debug("THEME: user=%s pressed=%r topics_labels=%s", user_id, text, list(topics_map.keys()))
        
            theme_key = topics_map.get(text.strip())
            if not theme_key:
                await update.message.reply_text(await tr(user, "wrong_theme"))
                return
        
            try:
                await update_user_theme(user_id, theme_key)
                await update_user_state(user_id, "sub")
                user = await get_user(user_id)
            except Exception:
                logger.exception("Failed to set theme/sub for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить тему. Попробуйте /start.")
                return
        
            subtopics = TOPICS[theme_key] + ["any_sub"]
            keyboard = [[await tr(user, s)] for s in subtopics]
            keyboard.append([await tr(user, "btn_main_menu")])
            await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return
        
        # --- Подтема ---
        if state == "sub":
            # кнопка назад
            if text.strip() == (await tr(user, "btn_main_menu")).strip():
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to return to menu from sub for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте /start.")
                return
        
            theme = user.get("theme")
            valid_sub_keys = TOPICS.get(theme, []) + ["any_sub"]
        
            # mapping: translated -> sub_key
            sub_map = {}
            for sk in valid_sub_keys:
                try:
                    lab = (await tr(user, sk)) or sk
                except Exception:
                    logger.exception("tr() failed for sub key %s (user=%s)", sk, user_id)
                    lab = sk
                sub_map[lab.strip()] = sk
        
            logger.debug("SUB: user=%s pressed=%r sub_labels=%s", user_id, text, list(sub_map.keys()))
        
            matched_sub = sub_map.get(text.strip())
            if not matched_sub:
                await update.message.reply_text(await tr(user, "wrong_sub"))
                return
        
            try:
                await update_user_sub(user_id, matched_sub)
                await update_user_state(user_id, "menu_after_sub")
                user = await get_user(user_id)
            except Exception:
                logger.exception("Failed to set sub/menu_after_sub for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить подбор. Попробуйте /start.")
                return
        
            await update.message.reply_text(
                f"{await tr(user, 'confirm_theme', theme=await tr(user, theme))}\n"
                f"{await tr(user, 'confirm_sub', sub=await tr(user, matched_sub))}",
                reply_markup=await kb_after_sub(user)
            )
            return

        # --- Меню после подтемы ---
        if state == "menu_after_sub":
            if text == await tr(user, "btn_search"):
                try:
                    await update_user_state(user_id, "searching")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "searching"), reply_markup=await kb_searching(user))
                    await add_to_queue(user_id, user["theme"], user["sub"], context)
                except Exception:
                    logger.exception("Search setup failed for user %s", user_id)
                    await update.message.reply_text(await tr(user, "search_failed"), reply_markup=await kb_after_sub(user))
                return

            if text == await tr(user, "btn_change_sub"):
                try:
                    await update_user_state(user_id, "sub")
                    user = await get_user(user_id)
                    subtopics = TOPICS[user["theme"]] + ["any_sub"]
                    keyboard = [[await tr(user, s)] for s in subtopics]
                    await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
                except Exception:
                    logger.exception("Failed to change sub for user %s", user_id)
                return

            if text == await tr(user, "btn_main_menu"):
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to return to menu from menu_after_sub for user %s", user_id)
                return

            if text == await tr(user, "btn_support"):
                await update.message.reply_text(await tr(user, "support_thanks"), reply_markup=await kb_after_sub(user))
                return

        # --- Поиск ---
        if state == "searching":
            if text == await tr(user, "btn_change_sub"):
                try:
                    await remove_from_queue(user_id)
                    await update_user_state(user_id, "sub")
                    user = await get_user(user_id)
                    sub_keys = TOPICS[user["theme"]] + ["any_sub"]
                    keyboard = [[await tr(user, s)] for s in sub_keys]
                    await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
                except Exception:
                    logger.exception("Failed to handle change_sub during search for user %s", user_id)
                return

            if text == await tr(user, "btn_main_menu"):
                try:
                    await remove_from_queue(user_id)
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "search_stopped"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to stop search for user %s", user_id)
                return

            if text == await tr(user, "btn_support"):
                await update.message.reply_text(await tr(user, "support_thanks"), reply_markup=await kb_searching(user))
                return

            await update.message.reply_text(await tr(user, "default_searching"))
            return

        # --- Чат ---
        if await is_in_chat(user_id):
            companion_id = user.get("companion_id")
            if text == await tr(user, "btn_end"):
                await end_dialog(user_id, context)
                return
            if text == await tr(user, "btn_new_partner"):
                await end_dialog(user_id, context, silent=True)
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to set state=menu after new_partner for user %s", user_id)
                return
            if companion_id:
                await context.bot.send_message(companion_id, text=text)
                await increment_messages(user_id)
                await increment_messages(companion_id)
            return

        # --- Предложения ---
        if state == "suggest":
            btn_main = await tr(user, "btn_main_menu")
            btn_settings = await tr(user, "btn_settings")
            btn_start = await tr(user, "btn_start_chat")
            btn_stats = await tr(user, "btn_stats")
            btn_vip = await tr(user, "btn_get_vip")
            btn_donate = await tr(user, "btn_donate")

            cancel_buttons = {btn_main, btn_settings, btn_start, btn_stats, btn_vip, btn_donate}

            if text in cancel_buttons:
                if text == btn_start:
                    try:
                        await update_user_state(user_id, "theme")
                        user = await get_user(user_id)
                        await update.message.reply_text(await tr(user, "pick_theme"), reply_markup=await get_topic_keyboard(user))
                    except Exception:
                        logger.exception("Failed to set state=theme from suggest for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return

                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to set state=menu from suggest for user %s", user_id)
                return

            if not text or text.startswith("/"):
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to cancel suggest for user %s", user_id)
                return

            admin_id = ADMIN_IDS[0] if (ADMIN_IDS and len(ADMIN_IDS) > 0) else None
            if admin_id:
                try:
                    await context.bot.send_message(chat_id=admin_id,
                        text=f"📩 Новое предложение от @{update.effective_user.username or user_id}:\n\n{text}")
                except Exception:
                    logger.exception("Failed to forward suggestion to admin")

            await update.message.reply_text(await tr(user, "suggest_thanks"))
            try:
                await update_user_state(user_id, "menu")
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
            except Exception:
                logger.exception("Failed to set state=menu after suggest for user %s", user_id)
            return

        # --- Фолбэк ---
        await update.message.reply_text(await tr(user, "error_fallback"))

    except Exception:
        logger.exception("Unhandled exception in message_handler")
        try:
            await update.message.reply_text("Произошла ошибка — попробуйте /start или сообщите администратору.")
        except Exception:
            logger.exception("Also failed to notify user after handler exception")
