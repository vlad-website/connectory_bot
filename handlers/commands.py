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
from core.i18n import tr, tr_lang

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
    user = await get_user(user_id)

    if not user:
        # зарегистрировать пользователя
        await create_user(user_id, lang="ru")  # или "en", если автоопределяешь
        await update_user_state(user_id, "nickname")
        await update.message.reply_text("Привет! Как тебя зовут?")
        return

    # 🔒 Пользователь не закончил регистрацию
    if user["state"] == "nickname":
        await update.message.reply_text(await tr(user, "enter_nick"))
        return
    elif user["state"] == "gender":
        await update.message.reply_text(await tr(user, "choose_gender"))
        return
    elif user["state"] == "theme":
        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(await tr(user, "pick_theme"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    elif user["state"] == "sub":
        subtopics = TOPICS[user["theme"]] + ["Любая подтема"]
        keyboard = [[s] for s in subtopics]
        await update.message.reply_text(await tr(user, "choose_sub"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ✅ Всё хорошо, пользователь зарегистрирован
    await update_user_state(user_id, "menu")
    await update.message.reply_text(
        await tr(user, "main_menu"),
        reply_markup=await kb_after_sub(user)
    )

# ---------- callback: выбор языка ----------
async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    user_id = query.from_user.id

    await create_user(user_id, lang)            # если запись уже есть – ON CONFLICT DO NOTHING
    await update_user_lang(user_id, lang)
    await update_user_state(user_id, "nickname")

    await query.message.delete()                # убираем меню языков

    await context.bot.send_message(
        chat_id=user_id,
        text=tr_lang(lang, "enter_nick")
    )

# ---------- регистрация ----------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
