# core/chat_control.py
import logging
from datetime import datetime

from db.user_queries import (
    get_user,
    update_user_state,
    update_user_companion,
    clear_chat_started,
)
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

    # ================================================================
    # 1️⃣ ФИКСАЦИЯ ВРЕМЕНИ: считаем минуту и сохраняем
    # ================================================================
    try:
        start = user.get("chat_started_at")
        if start:
            now = datetime.utcnow()
            minutes = int((now - start).total_seconds() // 60)

            if minutes > 0:
                await add_chat_minutes(user_id, minutes)

            await clear_chat_started(user_id)  # обнуляем
    except Exception:
        logger.exception("Failed to record chat time for %s", user_id)

    # То же самое для собеседника
    if companion_id:
        try:
            other = await get_user(companion_id)
            if other and other.get("chat_started_at"):
                now = datetime.utcnow()
                minutes = int((now - other["chat_started_at"]).total_seconds() // 60)

                if minutes > 0:
                    await add_chat_minutes(companion_id, minutes)

                await clear_chat_started(companion_id)
        except Exception:
            logger.exception("Failed to record chat time for companion %s", companion_id)

    # ================================================================
    # 2️⃣ Переводим обоих обратно в состояние menu_after_sub
    # ================================================================
    await update_user_state(user_id, "menu_after_sub")
    await update_user_companion(user_id, None)

    if companion_id:
        await update_user_state(companion_id, "menu_after_sub")
        await update_user_companion(companion_id, None)

    # ================================================================
    # 3️⃣ Уведомляем
    # ================================================================
    # Тихий режим — только уведомляем вторую сторону
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

    # Обычный режим
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
