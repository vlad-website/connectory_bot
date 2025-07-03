from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import os

THEME, MATCHING = range(2)
user_data = {}

THEMES = {
    "Книги и литература": ["Романы", "Детективы", "Приключения", "Другое"],
    "Фильмы и сериалы": ["Боевики", "Комедии", "Документальные", "Любое"],
    "Стартапы и бизнес": ["Идеи", "Поиск партнёров", "Нетворкинг", "Обсуждение"],
    "Технологии": ["AI", "Программирование", "Наука", "Другое"],
    "Психология и философия": ["Сознание", "Эмоции", "Размышления", "Всё подряд"],
    "Музыка": ["Рок", "Поп", "Классика", "Другое"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [[theme] for theme in THEMES]
    await update.message.reply_text(
        "Привет! Выбери тему для беседы:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return THEME

async def theme_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    theme = update.message.text
    if theme not in THEMES:
        await update.message.reply_text("Выбери тему из предложенных.")
        return THEME
    context.user_data["theme"] = theme

    reply_keyboard = [[sub] for sub in THEMES[theme]]
    await update.message.reply_text(
        f"Выбери подкатегорию для темы '{theme}':",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return MATCHING

async def match_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub = update.message.text
    theme = context.user_data.get("theme", "")
    context.user_data["subtheme"] = sub
    await update.message.reply_text(
        f"Отлично! Сейчас подберу тебе собеседника по теме '{theme}' — '{sub}'.
(пока в разработке)"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог отменён.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(os.getenv("TG_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            THEME: [MessageHandler(filters.TEXT & ~filters.COMMAND, theme_choice)],
            MATCHING: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
