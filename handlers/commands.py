import logging
from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler
)

from db.user_queries import (
    get_user, create_user, update_user_state,
    update_user_lang
)
from core.i18n import tr, tr_lang
from core.topics import TOPICS
from handlers.keyboards import kb_after_sub

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

    if not user or not user.get("lang"):
        # Определяем язык устройства
        device_lang = (update.effective_user.language_code or "ru").split("-")[0]
        if device_lang not in language_names:
            device_lang = "ru"

        # 💬 Приветственное сообщение на языке устройства
        welcome_messages = {
            "ru": "👋 Привет! Я бот для общения по интересам. Давай начнём — выбери язык:",
            "uk": "👋 Привіт! Я бот для спілкування за інтересами. Давай почнемо — обери мову:",
            "en": "👋 Hi! I'm a bot for chatting by interests. Let's start — choose a language:",
            "es": "👋 ¡Hola! Soy un bot para chatear según intereses. Empecemos — elige un idioma:",
            "de": "👋 Hallo! Ich bin ein Bot für Interessens-Chats. Lass uns anfangen – wähle eine Sprache:",
            "fr": "👋 Salut ! Je suis un bot pour discuter selon tes centres d'intérêt. Commençons — choisis une langue :"
        }

        await update.message.reply_text(
            welcome_messages.get(device_lang, welcome_messages["ru"]),
            reply_markup=kb_choose_lang()
        )
        return

        # 🔒 Продолжаем регистрацию
        state = user.get("state")
        lang = user.get("lang", "ru")

        if state == "nickname":
            await update.message.reply_text(await tr(user, "enter_nick"))
            return

        elif state == "gender":
            await update.message.reply_text(await tr(user, "choose_gender"))
            return

        elif state == "theme":
            # Переводим ключи тем
            topics_translated = [await tr(user, key) for key in TOPICS.keys()]
            keyboard = [[t] for t in topics_translated]

            await update.message.reply_text(
                await tr(user, "pick_theme"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        elif state == "sub":
            theme_key = user.get("theme")
            subtopics_keys = TOPICS.get(theme_key, []) + ["any_sub"]
            subtopics_translated = [await tr(user, s) for s in subtopics_keys]

            keyboard = [[s] for s in subtopics_translated]
            await update.message.reply_text(
                await tr(user, "choose_sub"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        # ✅ Всё завершено — меню
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

    await create_user(user_id, lang)
    await update_user_lang(user_id, lang)
    await update_user_state(user_id, "nickname")

    await query.message.delete()

    await context.bot.send_message(
        chat_id=user_id,
        text=tr_lang(lang, "enter_nick")
    )

# ---------- регистрация ----------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
