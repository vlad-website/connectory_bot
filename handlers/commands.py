import logging, traceback

from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    CallbackContext, ContextTypes,
    CommandHandler, CallbackQueryHandler
)

from db.user_queries import (
    get_user, create_user, update_user_state,
    update_user_nickname, update_user_lang
)

logger = logging.getLogger(__name__)

# ---------------- Клавиатура выбора языка ----------------
def kb_choose_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton("🇺🇸 English",  callback_data="lang_en"),
         InlineKeyboardButton("🇪🇸 Español",  callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇩🇪 Deutsch",  callback_data="lang_de")],
    ])

language_names = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

# ---------------- /start ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        logger.info("▶️ /start for %s", user_id)

        user = await get_user(user_id)

        if user:
            nickname = user.get("nickname") or "друг"
            await update.message.reply_text(
                f"👋 С возвращением, {nickname}!",
                reply_markup=ReplyKeyboardMarkup([["Начать"]], resize_keyboard=True)
            )
        else:
            # нового пользователя просим выбрать язык
            await update.message.reply_text(
                "🌍 Пожалуйста, выберите язык:",
                reply_markup=kb_choose_lang()
            )

        logger.info("✅ /start replied OK for %s", user_id)

    except Exception as e:
        print("💥 EXCEPTION in /start:", e, flush=True)
        print(traceback.format_exc(), flush=True)
        logger.exception("Exception in /start")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте позже.")

# ---------------- Обработчик выбора языка ----------------
async def choose_lang(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()                       # закрываем «часики»

    user_id = query.from_user.id
    lang = query.data.split("_")[1]            # lang_ru → ru

    # создаём пользователя с выбранным языком
    await create_user(user_id, lang)
    await update_user_lang(user_id, lang)
    await update_user_state(user_id, "nickname")

    lang_name = language_names.get(lang, lang)
    await query.edit_message_text(
        f"✅ {lang_name} выбран.\n\n👋 Введи свой ник (имя, по которому тебя увидит собеседник):"
    )

# ---------------- Регистрация хендлеров ----------------
def register_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
