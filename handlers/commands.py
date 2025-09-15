import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from db.user_queries import get_user, create_user, update_user_state, update_user_lang
from core.i18n import tr_lang

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

# ---------------- /start ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    # --- Сбрасываем старое состояние ---
    if user:
        await update_user_state(user_id, "menu")
        user = await get_user(user_id)
        await update.message.reply_text(
            await tr(user, "main_menu"),
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
    return

# ---------- callback: выбор языка ----------
async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Гарантируем, что клиент увидит "обновление"
    try:
        await query.answer()
    except Exception:
        # если не удалось ответить — просто логируем и продолжаем
        logger.exception("Failed to answer callback_query")

    # Получаем код языка безопасно
    try:
        lang = query.data.split("_", 1)[1]
    except Exception:
        logger.error("Bad callback data: %s", query.data)
        try:
            await query.answer(text="Неверная кнопка", show_alert=True)
        except Exception:
            pass
        return

    user_id = query.from_user.id

    # Сохраняем данные в БД и переводим state — в try/except чтобы ловить ошибки БД
    try:
        await create_user(user_id, lang)
        await update_user_lang(user_id, lang)
        await update_user_state(user_id, "nickname")
    except Exception:
        logger.exception("Failed to create/update user for choose_lang (user=%s, lang=%s)", user_id, lang)
        # уведомляем пользователя о проблеме (попытка edit, затем отправка)
        try:
            await query.edit_message_text("❌ Ошибка сервера. Попробуйте /start позже.")
        except Exception:
            try:
                await context.bot.send_message(chat_id=user_id, text="❌ Ошибка сервера. Попробуйте /start позже.")
            except Exception:
                logger.exception("Also failed to notify user %s about DB error", user_id)
        return

    # Успешно — показываем сообщение о вводе ника (используем edit + fallback)
    try:
        await query.edit_message_text(tr_lang(lang, "enter_nick"))
    except Exception:
        # если edit не сработал (например, сообщение удалено или в другом контексте) — шлём новое
        try:
            await context.bot.send_message(chat_id=user_id, text=tr_lang(lang, "enter_nick"))
        except Exception:
            logger.exception("Failed to send enter_nick message to user %s", user_id)

# ---------- регистрация обработчиков ----------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"))
