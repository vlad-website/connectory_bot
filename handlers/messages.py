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
from config import ADMIN_IDS  # список ID админов

logger = logging.getLogger(__name__)

async def get_topic_keyboard(user):
    """Создаёт клавиатуру выбора тем с переводом."""
    topic_keys = [await tr(user, k) for k in TOPICS.keys()]
    keyboard = [[k] for k in topic_keys]
    keyboard.append([await tr(user, "btn_main_menu")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def handle_stop_search(user_id, user, context):
    """Обработка кнопки 'Остановить поиск'."""
    await remove_from_queue(user_id)
    task = active_search_tasks.pop(user_id, None)
    if task:
        try: task.cancel()
        except: pass

    await update_user_state(user_id, "menu_after_sub")
    user = await get_user(user_id)
    stopped_msg = await tr(user, "search_stopped")
    await context.bot.send_message(
        chat_id=user_id,
        text=stopped_msg,
        reply_markup=await kb_after_sub(user)
    )



async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    user = await get_user(user_id)

    if not user:
        await update.message.reply_text("⚠️ Нажмите /start")
        return

    state = user.get("state")

    # --- Регистрация никнейма ---
    if state == "nickname":
        await update_user_nickname(user_id, text)
        await update_user_state(user_id, "gender")
        user = await get_user(user_id)
        keyboard = [[await tr(user, "gender_male")],
                    [await tr(user, "gender_female")],
                    [await tr(user, "gender_any")]]
        await update.message.reply_text(await tr(user, "choose_gender"),
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # --- Выбор пола ---
    if state == "gender":
        # если уже указан, просто переводим в меню
        if user.get("gender"):
            await update_user_state(user_id, "menu")
            user = await get_user(user_id)
            await update.message.reply_text(await tr(user, "main_menu"),
                                            reply_markup=await kb_main_menu(user))
            return

        valid_genders = [await tr(user, "gender_male"),
                         await tr(user, "gender_female"),
                         await tr(user, "gender_any")]
        if text not in valid_genders:
            await update.message.reply_text(await tr(user, "wrong_gender"),
                                            reply_markup=ReplyKeyboardMarkup([[g] for g in valid_genders],
                                                                             resize_keyboard=True))
            return

        # Сохраняем пол и сразу обновляем user из БД
        await update_user_gender(user_id, text)
        await update_user_state(user_id, "menu")
        user = await get_user(user_id)
        await update.message.reply_text(await tr(user, "main_menu"),
                                        reply_markup=await kb_main_menu(user))
        return


    # --- Главное меню ---
    if state == "menu":
        menu_actions = {
            await tr(user, "btn_start_chat"): "theme",
            await tr(user, "btn_stats"): "stats",
            await tr(user, "btn_settings"): "settings",
            await tr(user, "btn_suggest"): "suggest",
            await tr(user, "btn_get_vip"): "vip",
            await tr(user, "btn_donate"): "donate",
        }

        # Проверка кнопки и переход
        if text in menu_actions:
            action = menu_actions[text]

            if action == "theme":
                # 🔥 фикс: при выборе темы сбрасываем возможный старый стейт (например, suggest)
                await update_user_state(user_id, "theme")
                user = await get_user(user_id)
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
                await update_user_state(user_id, "suggest")
                await update.message.reply_text(await tr(user, "pls_suggest"))
                return
            elif action == "vip":
                await update.message.reply_text(await tr(user, "vip_soon"))
                return
            elif action == "donate":
                await update.message.reply_text(await tr(user, "donate_thanks"))
                return

        # Админская статистика
        if text == "📊 Админ статистика":
            if user_id in ADMIN_IDS:
                await send_admin_stats(update, context)
            else:
                await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
            return

    

    # --- Тема и подтема ---
    if state == "theme":
        if text == await tr(user, "btn_main_menu"):
            await update_user_state(user_id, "menu")
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
    
        await update_user_theme(user_id, theme_key)
        await update_user_state(user_id, "sub")
    
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
            await update_user_state(user_id, "menu")
            await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
            return

        theme = user.get("theme")
        valid_sub_keys = TOPICS.get(theme, []) + ["any_sub"]
        valid_subs = [await tr(user, s) for s in valid_sub_keys]
        if text not in valid_subs:
            await update.message.reply_text(await tr(user, "wrong_sub"))
            return

        sub_key = valid_sub_keys[valid_subs.index(text)]
        await update_user_sub(user_id, sub_key)
        await update_user_state(user_id, "menu_after_sub")
        await update.message.reply_text(
            f"{await tr(user, 'confirm_theme', theme=await tr(user, theme))}\n"
            f"{await tr(user, 'confirm_sub', sub=await tr(user, sub_key))}",
            reply_markup=await kb_after_sub(user)
        )
        return

    # --- Меню после выбора подтемы ---
    if state == "menu_after_sub":
        if text == await tr(user, "btn_search"):
            await update_user_state(user_id, "searching")
            await update.message.reply_text(await tr(user, "searching"), reply_markup=await kb_searching(user))
            await add_to_queue(user_id, user["theme"], user["sub"], context)
            return
        elif text == await tr(user, "btn_change_sub"):
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + ["any_sub"]
            keyboard = [[await tr(user, s)] for s in subtopics]
            update_message = await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return
        elif text == await tr(user, "btn_main_menu"):
            await update_user_state(user_id, "menu")
            await update.message.reply_text(await tr(user, "main_menu"), reply_markup=await kb_main_menu(user))
            return
        elif text == await tr(user, "btn_support"):
            await update.message.reply_text(await tr(user, "support_thanks"), reply_markup=await kb_after_sub(user))
            return


    

    # --- Поиск партнёра ---
    if state == "searching":
        if text == await tr(user, "btn_change_sub"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "sub")
            sub_keys = TOPICS[user["theme"]] + ["any_sub"]
            keyboard = [[await tr(user, s)] for s in sub_keys]
            await update.message.reply_text(await tr(user, "choose_sub"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return
        if text == await tr(user, "btn_main_menu"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "menu")
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
            await update_user_state(user_id, "menu")
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
                await update_user_state(user_id, "theme")
                user = await get_user(user_id)
                await update.message.reply_text(
                    await tr(user, "pick_theme"),
                    reply_markup=await get_topic_keyboard(user)
                )
                return
    
            # во всех остальных случаях возвращаем главное меню
            await update_user_state(user_id, "menu")
            user = await get_user(user_id)
            from handlers.keyboards import kb_main_menu
            await update.message.reply_text(
                await tr(user, "main_menu"),
                reply_markup=await kb_main_menu(user)
            )
            return
    
        # не присылаем пустые сообщения или команды
        if not text or text.startswith("/"):
            # можно отправить сообщение-отмену (перевод добавь в словарь, ключ например "suggest_cancelled")
            # или просто вернуть в главное меню
            await update_user_state(user_id, "menu")
            user = await get_user(user_id)
            from handlers.keyboards import kb_main_menu
            await update.message.reply_text(
                await tr(user, "main_menu"),
                reply_markup=await kb_main_menu(user)
            )
            return
    
        # Всё проверено — отправляем предложение админу
        admin_id = ADMIN_IDS[0] if (globals().get("ADMIN_IDS") and len(ADMIN_IDS) > 0) else None
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 Новое предложение от @{update.effective_user.username or user_id}:\n\n{text}"
                )
            except Exception:
                logger.exception("Failed to forward suggestion to admin")
    
        await update.message.reply_text(await tr(user, "suggest_thanks"))
        await update_user_state(user_id, "menu")
        user = await get_user(user_id)
        from handlers.keyboards import kb_main_menu
        await update.message.reply_text(
            await tr(user, "main_menu"),
            reply_markup=await kb_main_menu(user)
        )
        return

    # --- Фолбэк ---
    await update.message.reply_text(await tr(user, "error_fallback"))
