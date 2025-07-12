from db.user_queries import get_user, update_user_state, update_user_companion
from handlers.keyboards import kb_after_sub          # ← клавиатура после диалога
from telegram import Bot

async def end_dialog(user_id: int, context, silent: bool = False):
    """
    Завершить диалог.
    silent=True — не уведомлять вторую сторону (используется для «Новый собеседник»).
    """
    user = await get_user(user_id)
    if not user:
        return

    companion_id = user.get("companion_id")

    # переводим текущего пользователя в меню
    await update_user_state(user_id, "menu")
    await update_user_companion(user_id, None)

    # переводим собеседника, если есть
    if companion_id:
        await update_user_state(companion_id, "menu")
        await update_user_companion(companion_id, None)

    # отправляем сообщения, если не silent
    if not silent:
        await context.bot.send_message(
            user_id,
            "💬 Диалог завершён.",
            reply_markup=kb_after_sub()
        )
        if companion_id:
            await context.bot.send_message(
                companion_id,
                "❌ Собеседник завершил диалог.",
                reply_markup=kb_after_sub()
            )
