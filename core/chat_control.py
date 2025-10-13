# core/chat_control.py
import logging
from db.user_queries import get_user, update_user_state, update_user_companion
from handlers.keyboards import kb_after_sub

logger = logging.getLogger(__name__)

async def end_dialog(user_id: int, context, silent: bool = False):
    """
    Завершить диалог.
    silent=True — не уведомлять инициатора (используется для «Новый собеседник»).
    """
    user = await get_user(user_id)
    if not user:
        return

    companion_id = user.get("companion_id")

    # переводим текущего пользователя в меню
    await update_user_state(user_id, "after_sub")
    await update_user_companion(user_id, None)

    # переводим собеседника, если есть
    if companion_id:
        await update_user_state(companion_id, "after_sub")
        await update_user_companion(companion_id, None)

    # Тихий режим — только сообщаем второй стороне об отключении (без details)
    if silent:
        if companion_id:
            other = await get_user(companion_id)
            try:
                await context.bot.send_message(
                    companion_id,
                    "💬 Собеседник отключился.",
                    reply_markup=await kb_after_sub(other) if other else None
                )
            except Exception:
                logger.exception("Failed to notify companion %s about silent end", companion_id)
        return

    # Обычный режим — уведомляем обе стороны
    try:
        await context.bot.send_message(
            user_id,
            "💬 Диалог завершён.",
            reply_markup=await kb_after_sub(user)
        )
    except Exception:
        logger.exception("Failed to notify user %s about dialog end", user_id)

    if companion_id:
        other = await get_user(companion_id)
        try:
            await context.bot.send_message(
                companion_id,
                "❌ Собеседник завершил диалог.",
                reply_markup=await kb_after_sub(other) if other else None
            )
        except Exception:
            logger.exception("Failed to notify companion %s about dialog end", companion_id)
