from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from db.user_queries import update_user_theme, update_user_sub, update_user_state
from core.topics import TOPICS
from db.user_queries import get_user
from core.matchmaking import add_to_queue, is_in_chat
from core.chat_control import end_dialog

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("💬 MSG:", update.message.text)      # ← временно
    user_id = update.effective_user.id
    user = await get_user(user_id)
    text = update.message.text.strip()

    if not user:
        await update.message.reply_text("Пожалуйста, отправьте /start.")
        return

    state = user["state"]

    if state == "nickname":
    # 1. сохраняем ник
        await update_user_nickname(user_id, text)

    # 2. проверяем, что ник действительно записан
    user_after = await get_user(user_id)
    logger.debug("After nickname update: %s", user_after)   # должен показать nickname != None

    # 3. переводим пользователя к выбору пола
    await update_user_state(user_id, "gender")

    await update.message.reply_text("Укажи свой пол (М/Ж):")
    return  # ← ОБЯЗАТЕЛЬНО остановить дальнейший код
    
    elif state == "gender":
        if text.lower() in ("м", "муж", "мужской"):
            gender = "М"
        elif text.lower() in ("ж", "жен", "женский"):
            gender = "Ж"
        else:
            await update.message.reply_text("Пожалуйста, укажи пол — М или Ж:")
            return
        await update_user_gender(user_id, gender)
        await update_user_state(user_id, "theme")

        # Выбор темы
        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(
            "Выбери интересующую тебя тему:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif state == "theme":
        if text not in TOPICS:
            await update.message.reply_text("Пожалуйста, выбери тему из списка.")
            return
        await update_user_theme(user_id, text)
        await update_user_state(user_id, "sub")

        # Подтемы + "любая"
        subtopics = TOPICS[text] + ["Любая подтема"]
        keyboard = [[s] for s in subtopics]
        await update.message.reply_text(
            "Теперь выбери подтему:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif state == "sub":
        theme = user["theme"]
        valid_subs = TOPICS.get(theme, []) + ["Любая подтема"]
        if text not in valid_subs:
            await update.message.reply_text("Выбери подтему из списка.")
            return
        await update_user_sub(user_id, text)
        await update_user_state(user_id, "searching")
        await update.message.reply_text("🔎 Ищу собеседника...")

        await add_to_queue(user_id, theme, text)

    elif state == "searching":
        await update.message.reply_text("⏳ Поиск собеседника...")

    elif await is_in_chat(user_id):
        # Уже в чате — просто пересылай
        await context.bot.send_message(chat_id=user["companion_id"], text=text)
    else:
        await update.message.reply_text("❌ Что-то пошло не так. Напиши /start.")



    if text == "Завершить диалог":
        await end_dialog(user_id, context)
        return

    elif text == "Главное меню":
        await update_user_state(user_id, "theme")
        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(
            "Выбери интересующую тему:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    elif text == "Поддержать проект ❤️":
        await update.message.reply_text(
            "🙏 Спасибо за желание поддержать проект!\n(Заглушка, здесь может быть ссылка на донат 💸)"
        )
        return




