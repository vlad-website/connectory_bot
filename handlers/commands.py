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

    if user:
        text = await tr(user, "welcome_back", name=user.get("nickname") or "друг")
        btn  = await tr(user, "btn_start")
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True)
        )
    else:
        device_lang = (update.effective_user.language_code or "ru").split("-")[0]
        if device_lang not in language_names:
            device_lang = "ru"
        await update.message.reply_text(
            tr_lang(device_lang, "choose_lang"),
            reply_markup=kb_choose_lang()
        )

# ---------- callback: выбор языка ----------
async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    user_id = query.from_user.id

    await create_user(user_id, lang)
    await update_user_lang(user_id, lang)
    await update_user_state(user_id, "nickname")

    await query.edit_message_text(
        tr_lang(lang, "enter_nick")
    )

# ---------- регистрация ----------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
