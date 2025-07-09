from db.user_queries import get_user, update_user_state, update_user_companion
from telegram import Bot, ReplyKeyboardMarkup

async def end_dialog(user_id, context):
    user = await get_user(user_id)
    if not user:
        return

    companion_id = user.get("companion_id")

    await update_user_state(user_id, "theme")
    await update_user_companion(user_id, None)

    if companion_id:
        await update_user_state(companion_id, "theme")
        await update_user_companion(companion_id, None)

        await context.bot.send_message(
            companion_id,
            "❌ Собеседник завершил диалог.",
            reply_markup=ReplyKeyboardMarkup([["Начать заново"]], resize_keyboard=True)
        )

    await context.bot.send_message(
        user_id,
        "💬 Диалог завершён.",
        reply_markup=ReplyKeyboardMarkup([["Начать заново"]], resize_keyboard=True)
    )
