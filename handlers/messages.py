import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.keyboards import kb_settings, kb_gender_settings, kb_after_sub, kb_chat, kb_searching, kb_main_menu, get_topic_keyboard
from handlers.keyboards import kb_choose_lang
from core.i18n import tr
from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_lang, update_user_sub, update_user_state,
    increment_messages
)
from core.topics import TOPICS
from core.matchmaking import add_to_queue, remove_from_queue, active_search_tasks, is_in_chat
from core.chat_control import end_dialog
from handlers.admin import send_admin_stats
from config import ADMIN_IDS

from telegram import InlineKeyboardButton, InlineKeyboardMarkup





logger = logging.getLogger(__name__)

# --- Глобальный кэш для текстов перевода ---
TRANSLATION_CACHE = {}



# 🔹 Добавляем сюда — новую версию handle_stop_search
async def handle_stop_search(user_id: int, user: dict, context):
    try:
        # убираем пользователя из очереди поиска
        await remove_from_queue(user_id)

        # возвращаем состояние в menu_after_sub (чтобы мог снова нажать "Поиск")
        await update_user_state(user_id, "menu_after_sub")
        user = await get_user(user_id)

        await context.bot.send_message(
            user_id,
            await tr(user, "search_stopped"),
            reply_markup=await kb_after_sub(user)
        )
    except Exception:
        logger.exception("Failed to stop search for user %s", user_id)

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


        # --- Чат ---
        if await is_in_chat(user_id):
            # обновим user — после матча в БД companion_id может появиться
            user = await get_user(user_id)
            companion_id = user.get("companion_id")
        
            # правильная проверка на кнопку завершения — используем тот ключ, что в kb_chat
            if text == await tr(user, "btn_end_chat"):
                await end_dialog(user_id, context)
                return
        
            if text == await tr(user, "btn_new_partner"):
                # пользователь хочет нового партнёра — тихо закрываем текущий диалог
                await end_dialog(user_id, context, silent=True)
                user = await get_user(user_id)
                # вернём пользователя в меню (и покажем главное меню)
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                except Exception:
                    logger.exception("Failed to set state=menu after new_partner for user %s", user_id)
                return
        
            # если есть компаньон — пересылаем текст
            if companion_id:
                try:
                    from uuid import uuid4
                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
                    companion = await get_user(companion_id)
                    lang_from = user.get("lang", "en")
                    lang_to = companion.get("lang", "en")
            
                    # --- создаём короткий ключ и сохраняем текст в контекст ---
                    translation_key = str(uuid4())[:8]
                    TRANSLATION_CACHE[translation_key] = text
            
                    # --- создаём inline-кнопку, только если языки разные ---
                    reply_markup = None
                    if lang_from != lang_to:
                        reply_markup = InlineKeyboardMarkup([[
                            InlineKeyboardButton(
                                "🌐 Показать перевод",
                                callback_data=f"tr|{lang_from}|{lang_to}|{translation_key}"
                            )
                        ]])
            
                    # --- отправляем сообщение ---
                    await context.bot.send_message(
                        chat_id=companion_id,
                        text=text,
                        reply_markup=reply_markup
                    )
            
                    # --- обновляем статистику сообщений ---
                    await increment_messages(user_id)
                    await increment_messages(companion_id)
            
                except Exception:
                    logger.exception("Failed to forward chat message from %s to %s", user_id, companion_id)
                return

        

        
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
                        # 1️⃣ Сначала обновляем состояние
                        await update_user_state(user_id, "theme")
                    
                        # 2️⃣ Обновляем пользователя, чтобы гарантировать правильный язык и состояние
                        user = await get_user(user_id)
                    
                        # 3️⃣ Отправляем клавиатуру выбора темы
                        try:
                            from handlers.keyboards import get_topic_keyboard
                            markup = await get_topic_keyboard(user)
                    
                            await update.message.reply_text(
                                await tr(user, "pick_theme"),  # <-- правильный ключ перевода
                                reply_markup=markup
                            )
                    
                            logger.debug("STATE CHANGE: user=%s set to 'theme' from 'menu'", user_id)

                        except Exception:
                            # если клавиатура/тема упали — логируем и даём понятное сообщение
                            logger.exception("Failed to send topic keyboard to user %s", user_id)
                            await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")
                    elif action == "stats":
                        await update.message.reply_text(await tr(user, "stats_in_progress"))
                    elif action == "settings":
                        # Переводим пользователя в состояние settings
                        await update_user_state(user_id, "settings")
                    
                        # Обновляем user после смены состояния
                        user = await get_user(user_id)
                    
                        from handlers.keyboards import kb_settings
                    
                        await update.message.reply_text(
                            await tr(user, "settings_title"),
                            reply_markup=await kb_settings(user)
                        )
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


        # --- AFTER_SUB ---
        elif state == "after_sub":
            text = update.message.text
            logger.debug("AFTER_SUB: user=%s text=%r", user_id, text)
        
            if text == await tr(user, "btn_search"):
                try:
                    await update_user_state(user_id, "searching")
                    await update.message.reply_text(
                        await tr(user, "searching_message"),
                        reply_markup=await kb_searching(user)
                    )
                    # запускаем поиск
                    await add_to_queue(user_id, user["theme"], user["sub"], context)
        
                except Exception:
                    logger.exception("Search setup failed for user %s", user_id)
                    # НЕ сбрасываем клавиатуру, просто даём мягкое уведомление
                    await update.message.reply_text(
                        await tr(user, "searching_retry")
                    )
                return
        
            elif text == await tr(user, "btn_change_sub"):
                await update_user_state(user_id, "choose_sub")
                await update.message.reply_text(await tr(user, "choose_sub"))
                return
        
            elif text == await tr(user, "btn_main_menu"):
                await update_user_state(user_id, "menu")
                await update.message.reply_text(
                    await tr(user, "main_menu"),
                    reply_markup=await kb_main_menu(user)
                )
                return
        
            elif text == await tr(user, "btn_support"):
                await update.message.reply_text(await tr(user, "support_message"))
                return
        
            else:
                await update.message.reply_text(await tr(user, "pls_start"))
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



        # --- Настройки профиля ---
        if state == "settings":
            # Изменить язык -> уходим в под-состояние и показываем inline-кнопки
            if text == await tr(user, "btn_change_lang"):
                await update_user_state(user_id, "settings_lang")
                await update.message.reply_text(await tr(user, "pick_language"), reply_markup=kb_settings_lang())
                return
        
            # Изменить ник -> ждём следующий текст
            if text == await tr(user, "btn_change_name"):
                await update_user_state(user_id, "settings_name")
                await update.message.reply_text(await tr(user, "ask_new_name"))
                return
        
            # Изменить пол -> показываем клавиатуру полов
            if text == await tr(user, "btn_change_gender"):
                await update_user_state(user_id, "settings_gender")
                await update.message.reply_text(
                    await tr(user, "btn_change_gender"),
                    reply_markup=await kb_gender_settings(user)
                )
                return
        
            # Назад/Главное меню из настроек
            if text in (await tr(user, "btn_main_menu"), await tr(user, "settings_back")):
                await update_user_state(user_id, "menu")
                user = await get_user(user_id)
                await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
                return

        # --- Смена языка (ждём callback от inline-кнопок) ---
        if state == "settings_lang":
            # пользователь нажал обычную клавиатуру или что-то прислал
            # мы НИКОГДА не принимаем текст, только callback "setlang_xx"
            await update.message.reply_text(await tr(user, "pick_language"), reply_markup=kb_settings_lang())
            return

        # --- Ввод нового ника ---
        if state == "settings_name":
            new_name = (text or "").strip()[:30]
            if not new_name:
                await update.message.reply_text(await tr(user, "ask_new_name"))
                return
            await update_user_nickname(user_id, new_name)
            await update_user_state(user_id, "menu")
            user = await get_user(user_id)
            await update.message.reply_text(await tr(user, "name_changed"), reply_markup=await kb_main_menu(user))
            return

        # --- Выбор пола ---
        if state == "settings_gender":
            # Сопоставим ввод с ключами
            if text == await tr(user, "gender_male"):
                gender_value = "male"
            elif text == await tr(user, "gender_female"):
                gender_value = "female"
            elif text == await tr(user, "gender_other"):
                gender_value = "other"
            elif text == await tr(user, "settings_back"):
                await update_user_state(user_id, "settings")
                await update.message.reply_text(await tr(user, "settings_title"), reply_markup=await kb_settings(user))
                return
            else:
                # Нажал что-то левое — повторим клавиатуру
                await update.message.reply_text(await tr(user, "btn_change_gender"), reply_markup=await kb_gender_settings(user))
                return
        
            await update_user_gender(user_id, gender_value)
            await update_user_state(user_id, "menu")
            user = await get_user(user_id)
            await update.message.reply_text(await tr(user, "gender_changed"), reply_markup=await kb_main_menu(user))
            return

        
        # --- Меню после подтемы ---
        if state == "menu_after_sub":
            if text == await tr(user, "btn_search"):
                # 1) переводим в searching и показываем клавиатуру поиска — это вне try
                await update_user_state(user_id, "searching")
                user = await get_user(user_id)
                await update.message.reply_text(
                    await tr(user, "searching_message"),
                    reply_markup=await kb_searching(user)
                )
        
                # 2) пытаемся поставить в очередь/сматчить
                try:
                    await add_to_queue(user_id, user["theme"], user["sub"], context)
                except Exception:
                    logger.exception("Queue/match failed for user %s", user_id)
                    # 3) ПЕРЕПРОВЕРКА: вдруг нас уже перевели в chatting до ошибки?
                    user = await get_user(user_id)
                    if user and user.get("state") == "chatting":
                        # Пара уже найдена, ничего не трогаем
                        return

                                # Если всё-таки не в чате — мягко возвращаемся к меню после подтемы
                    await update_user_state(user_id, "menu_after_sub")
                    user = await get_user(user_id)
                    await update.message.reply_text(
                        await tr(user, "search_failed"),
                        reply_markup=await kb_after_sub(user)
                    )
                return
        
            if text == await tr(user, "btn_change_sub"):
                try:
                    await update_user_state(user_id, "sub")
                    user = await get_user(user_id)
                    subtopics = TOPICS[user["theme"]] + ["any_sub"]
                    keyboard = [[await tr(user, s)] for s in subtopics]
                    # 👉 Добавляем "Главное меню", чтобы можно было вернуться
                    keyboard.append([await tr(user, "btn_main_menu")])
                    await update.message.reply_text(
                        await tr(user, "choose_sub"),
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    )
                except Exception:
                    logger.exception("Failed to change sub for user %s", user_id)
                return
        
            if text == await tr(user, "btn_change_theme"):
                try:
                    await update_user_state(user_id, "theme")
                    user = await get_user(user_id)
        
                    from handlers.keyboards import get_topic_keyboard
                    markup = await get_topic_keyboard(user)
        
                    await update.message.reply_text(
                        await tr(user, "choose_theme"),  # ты добавил этот ключ — оставляем его
                        reply_markup=markup
                    )
                    return  # критично важно, чтобы не ловить это сообщение снова
                except Exception:
                    logger.exception("Failed to change theme for user %s", user_id)
                    await update.message.reply_text("❌ Ошибка при смене темы. Попробуйте /start.")
                return
        
            if text == await tr(user, "btn_main_menu"):
                try:
                    await update_user_state(user_id, "menu")
                    user = await get_user(user_id)
                    await update.message.reply_text(
                        await tr(user, "main_menu"),
                        reply_markup=await kb_main_menu(user)
                    )
                except Exception:
                    logger.exception("Failed to return to menu from menu_after_sub for user %s", user_id)
                return
        
            if text == await tr(user, "btn_support"):
                await update.message.reply_text(
                    await tr(user, "support_thanks"),
                    reply_markup=await kb_after_sub(user)
                )
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



        
        # --- Безопасный возврат в меню ---
        if user and user.get("state") == "menu":
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




# 👇 А вот здесь добавляешь обработчик inline-кнопок:
from telegram import Update
from telegram.ext import ContextTypes
from core.translator import translate_text
import asyncio
import html
import logging

logger = logging.getLogger(__name__)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # если нет данных — выходим
    if not query or not data:
        return

    # Выбор языка из настроек: callback_data = "lang_ru", "lang_en", ...
    # --- смена языка в настройках ---
    if data.startswith("setlang_"):
        lang = data.split("_")[1]
        user_id = query.from_user.id
    
        await update_user_lang(user_id, lang)
        user = await get_user(user_id)
    
        # возвращаем состояние обратно в настройки
        await update_user_state(user_id, "settings")
    
        # редактируем старое сообщение
        try:
            await query.message.edit_text(
                tr_lang(lang, "lang_changed")
            )
        except Exception:
            await context.bot.send_message(
                user_id, tr_lang(lang, "lang_changed")
            )
    
        # показываем обратно меню настроек
        from handlers.keyboards import kb_settings
        await context.bot.send_message(
            chat_id=user_id,
            text=await tr(user, "settings_title"),
            reply_markup=await kb_settings(user)
        )
    
        await query.answer()
        return

    # обрабатываем только кнопки перевода
    if not data.startswith("tr|"):
        await query.answer()
        return

    try:
        # формат теперь: tr|src_lang|dst_lang|uuid
        _, src_lang, dst_lang, key = data.split("|", 3)
    except ValueError:
        await query.answer("Ошибка данных кнопки", show_alert=True)
        return

    # достаем сохранённый текст по ключу
    text_to_translate = TRANSLATION_CACHE.get(key)
    if not text_to_translate:
        await query.answer("⚠️ Текст больше не доступен.")
        return

    # моментальный ответ
    await query.answer("Перевожу…")

    async def send_translation():
        try:
            translated = await translate_text(text_to_translate, src_lang, dst_lang)
            # после успешного перевода
            TRANSLATION_CACHE.pop(key, None)
            if not translated:
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text="⚠️ Не удалось перевести, попробуйте позже."
                )
                return

            escaped_src = html.escape(src_lang)
            escaped_dst = html.escape(dst_lang)
            escaped_text = html.escape(translated)

            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"💬 <b>Перевод ({escaped_src} → {escaped_dst}):</b>\n{escaped_text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.exception("Translation failed: %s", e)
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text="⚠️ Ошибка перевода, попробуйте позже."
            )

    # запускаем перевод в фоне, чтобы не блокировать Telegram
    asyncio.create_task(send_translation())
