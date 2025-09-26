from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from db.user_queries import get_user, create_user, update_user_state, update_user_lang
from handlers.keyboards import kb_main_menu
from core.i18n import tr_lang
import logging

logger = logging.getLogger(__name__)

def kb_choose_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
         InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    # --- Сброс старого состояния для зарегистрированного пользователя ---
    if user and user.get("lang"):
        await update_user_state(user_id, "menu")
        user = await get_user(user_id)
        await update.message.reply_text(
            tr_lang(user["lang"], "main_menu"),
            reply_markup=await kb_main_menu(user)
        )
        return

    # --- Новый пользователь или язык не выбран ---
    device_lang = (update.effective_user.language_code or "ru").split("-")[0]
    if device_lang not in ["ru", "uk", "en", "es", "fr", "de"]:
        device_lang = "ru"

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

async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]
    user_id = query.from_user.id

    # Создаём пользователя и выставляем state
    await create_user(user_id, lang)
    await update_user_lang(user_id, lang)
    await update_user_state(user_id, "nickname")

    await query.edit_message_text(tr_lang(lang, "enter_nick"))

def register_handlers(app):
    # Сначала команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
