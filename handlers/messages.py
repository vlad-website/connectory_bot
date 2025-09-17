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
        user = await get_user(user_id)
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
            # Прямо сохраняем ник и переводим в gender
            try:
                await update_user_nickname(user_id, text)
                await update_user_state(user_id, "gender")
            except Exception:
                logger.exception("Failed to save nickname for user %s", user_id)
                await update.message.reply_text("❌ Ошибка базы. Попробуйте ещё раз или /start")
                return

            # Обновим user из БД, чтобы иметь актуальную lang и пр.
            user = await get_user(user_id)
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
            # защита: если пол уже записан в БД — переводим в меню
            if user.get("gender"):
                logger.debug("User %s already has gender=%s — переход в menu", user_id, user.get("gender"))
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                user = await get_user(user_id)
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

            # запись пола — в try/except, затем обновляем user
            try:
                await update_user_gender(user_id, text)
                await update_user_state(user_id, "menu")
            except Exception:
                logger.exception("Failed to update gender for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить пол. Попробуйте ещё раз или /start")
                return

            user = await get_user(user_id)
            await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
            return


        # --- Главное меню ---
        if state == "menu":
            # Подготовим маппинг кнопок (переводы один раз)
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
        
            # Проверка кнопки и переход
            if text in menu_actions:
                action = menu_actions[text]
        
                if action == "theme":
                    try:
                        await update_user_state(user_id, "theme")
                    except Exception:
                        logger.exception("Failed to set state=theme for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                        return
                    user = await get_user(user_id)  # свежие данные
                    await update.message.reply_text(
                        await tr(user, "pick_theme"),
                        reply_markup=await get_topic_keyboard(user)
                    )
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
                    except Exception:
                        logger.exception("Failed to set state=suggest for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                        return
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "pls_suggest"))
                    return
        
                elif action == "vip":
                    await update.message.reply_text(await tr(user, "vip_soon"))
                    return
        
                elif action == "donate":
                    await update.message.reply_text(await tr(user, "donate_thanks"))
                    return
        
            # Админская статистика (фикс: проверяем текст напрямую)
            if text == "📊 Админ статистика":
                if user_id in ADMIN_IDS:
                    await send_admin_stats(update, context)
                else:
                    await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
                return
        
        
        # --- Тема и подтема ---
        if state == "theme":
            # кнопка возврата в меню
            if text == await tr(user, "btn_main_menu"):
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте /start.")
                    return
                user = await get_user(user_id)
                from handlers.keyboards import kb_main_menu
                await update.message.reply_text(
                    await tr(user, "main_menu"),
                    reply_markup=await kb_main_menu(user)
                )
                return
        
            # Определяем тему по переводу
            theme_key = None
            for key in TOPICS:
                translated = await tr(user, key)
                if text == translated or text == key:
                    theme_key = key
                    break
        
            if not theme_key:
                await update.message.reply_text(await tr(user, "wrong_theme"))
                return
        
            try:
                await update_user_theme(user_id, theme_key)
                await update_user_state(user_id, "sub")
            except Exception:
                logger.exception("Failed to set theme/sub for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить тему. Попробуйте ещё раз или /start.")
                return
        
            # Обновим user и сформируем клавиатуру подтем
            user = await get_user(user_id)
            subtopics = TOPICS[theme_key] + ["any_sub"]
            subtopics_translated = [await tr(user, s) for s in subtopics]
            keyboard = [[s] for s in subtopics_translated]
            keyboard.append([await tr(user, "btn_main_menu")])
        
            await update.message.reply_text(
                await tr(user, "choose_sub"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        if state == "sub":
            if text == await tr(user, "btn_main_menu"):
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте /start.")
                    return
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                return
        
            theme = user.get("theme")
            valid_sub_keys = TOPICS.get(theme, []) + ["any_sub"]
            valid_subs = [await tr(user, s) for s in valid_sub_keys]
            if text not in valid_subs:
                await update.message.reply_text(await tr(user, "wrong_sub"))
                return
        
            sub_key = valid_sub_keys[valid_subs.index(text)]
            try:
                await update_user_sub(user_id, sub_key)
                await update_user_state(user_id, "menu_after_sub")
            except Exception:
                logger.exception("Failed to set sub/menu_after_sub for user %s", user_id)
                await update.message.reply_text("❌ Не удалось сохранить подбор. Попробуйте ещё раз или /start.")
                return
        
            # обновим user перед формированием confirm текста и клавиатуры
            user = await get_user(user_id)
            await update.message.reply_text(
                f"{await tr(user, 'confirm_theme', theme=await tr(user, theme))}\n"
                f"{await tr(user, 'confirm_sub', sub=await tr(user, sub_key))}",
                reply_markup=await kb_after_sub(user)
            )
            return
        
        
        # --- Меню после выбора подтемы ---
        if state == "menu_after_sub":
            if text == await tr(user, "btn_search"):
                try:
                    await update_user_state(user_id, "searching")
                except Exception:
                    logger.exception("Failed to set state=searching for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return
        
                user = await get_user(user_id)  # свежие данные для kb_searching и очереди
                await update.message.reply_text(await tr(user, "searching"), reply_markup=await kb_searching(user))
        
                try:
                    await add_to_queue(user_id, user["theme"], user["sub"], context)
                except Exception:
                    logger.exception("add_to_queue failed for user %s", user_id)
                    # Попробуем откатить в меню_after_sub
                    try:
                        await update_user_state(user_id, "menu_after_sub")
                    except Exception:
                        logger.exception("Failed to rollback state to menu_after_sub for user %s", user_id)
                    await update.message.reply_text(await tr(user, "search_failed"), reply_markup=await kb_after_sub(user))
                return
        
            elif text == await tr(user, "btn_change_sub"):
                try:
                    await update_user_state(user_id, "sub")
                except Exception:
                    logger.exception("Failed to set state=sub for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return
                # обновим user, чтобы брать актуальную тему
                user = await get_user(user_id)
                subtopics = TOPICS[user["theme"]] + ["any_sub"]
                keyboard = [[await tr(user, s)] for s in subtopics]
                await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
                return
        
            elif text == await tr(user, "btn_main_menu"):
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте /start.")
                    return
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                return
        
            elif text == await tr(user, "btn_support"):
                await update.message.reply_text(await tr(user, "support_thanks"), reply_markup=await kb_after_sub(user))
                return
        
        
        # --- Поиск партнёра ---
        if state == "searching":
            if text == await tr(user, "btn_change_sub"):
                try:
                    await remove_from_queue(user_id)
                except Exception:
                    logger.exception("Failed to remove_from_queue for user %s", user_id)
                try:
                    await update_user_state(user_id, "sub")
                except Exception:
                    logger.exception("Failed to set state=sub for user %s", user_id)
                user = await get_user(user_id)
                sub_keys = TOPICS[user["theme"]] + ["any_sub"]
                keyboard = [[await tr(user, s)] for s in sub_keys]
                await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
                return
        
            if text == await tr(user, "btn_main_menu"):
                try:
                    await remove_from_queue(user_id)
                except Exception:
                    logger.exception("Failed to remove_from_queue for user %s", user_id)
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu for user %s", user_id)
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "search_stopped"), reply_markup=await kb_main_menu(user))
                return
        
            if text == await tr(user, "btn_support"):
                await update.message.reply_text(await tr(user, "support_thanks"), reply_markup=await kb_searching(user))
                return
        
            await update.message.reply_text(await tr(user, "default_searching"))
            return
        
        
        # --- Чат ---
        if await is_in_chat(user_id):
            if text == await tr(user, "btn_end"):
                await end_dialog(user_id, context)
                return
            if text == await tr(user, "btn_new_partner"):
                await end_dialog(user_id, context, silent=True)
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu after new_partner for user %s", user_id)
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                return
            companion_id = user.get("companion_id")
            if companion_id:
                await context.bot.send_message(companion_id, text=text)
                await increment_messages(user_id)
                await increment_messages(companion_id)
            return
        
        
        # --- Предложения ---
        if state == "suggest":
            # подготовим переводы кнопок для проверки (вызываем tr один раз)
            btn_main = await tr(user, "btn_main_menu")
            btn_settings = await tr(user, "btn_settings")
            btn_start = await tr(user, "btn_start_chat")
            btn_stats = await tr(user, "btn_stats")
            btn_vip = await tr(user, "btn_get_vip")
            btn_donate = await tr(user, "btn_donate")
        
            cancel_buttons = {btn_main, btn_settings, btn_start, btn_stats, btn_vip, btn_donate}
        
            # Если пользователь нажал одну из навигационных кнопок — отменяем режим suggest
            if text in cancel_buttons:
                # если нажал "Начать общение" — сразу переводим в state "theme"
                if text == btn_start:
                    try:
                        await update_user_state(user_id, "theme")
                    except Exception:
                        logger.exception("Failed to set state=theme from suggest for user %s", user_id)
                        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                        return
                    user = await get_user(user_id)
                    await update.message.reply_text(
                        await tr(user, "pick_theme"),
                        reply_markup=await get_topic_keyboard(user)
                    )
                    return
        
                # во всех остальных случаях возвращаем главное меню
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu from suggest for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    return
                user = await get_user(user_id)
                from handlers.keyboards import kb_main_menu
                await update.message.reply_text(
                    await tr(user, "main_menu"),
                    reply_markup=await kb_main_menu(user)
                )
                return
        
            # не присылаем пустые сообщения или команды
            if not text or text.startswith("/"):
                try:
                    await update_user_state(user_id, "menu")
                except Exception:
                    logger.exception("Failed to set state=menu when cancelling suggest for user %s", user_id)
                user = await get_user(user_id)
                from handlers.keyboards import kb_main_menu
                await update.message.reply_text(
                    await tr(user, "main_menu"),
                    reply_markup=await kb_main_menu(user)
                )
                return
        
            # Всё проверено — отправляем предложение админу
            admin_id = ADMIN_IDS[0] if (ADMIN_IDS and len(ADMIN_IDS) > 0) else None
            if admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📩 Новое предложение от @{update.effective_user.username or user_id}:\n\n{text}"
                    )
                except Exception:
                    logger.exception("Failed to forward suggestion to admin")
        
            await update.message.reply_text(await tr(user, "suggest_thanks"))
            try:
                await update_user_state(user_id, "menu")
            except Exception:
                logger.exception("Failed to set state=menu after suggest for user %s", user_id)
            user = await get_user(user_id)
            from handlers.keyboards import kb_main_menu
            await update.message.reply_text(
                await tr(user, "main_menu"),
                reply_markup=await kb_main_menu(user)
            )
            return

        # --- Фолбэк ---
        await update.message.reply_text(await tr(user, "error_fallback"))

    except Exception:
            logger.exception("Unhandled exception in message_handler")
            try:
                await update.message.reply_text("Произошла ошибка — попробуйте /start или сообщите администратору.")
            except Exception:
                logger.exception("Also failed to notify user after handler exception")
