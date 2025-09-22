from db.user_queries import get_user, update_user_state, update_user_companion
from handlers.keyboards import kb_main_menu
from core.i18n import tr

async def end_dialog(user_id: int, context, silent: bool = False):
    """
    Завершить диалог.
    silent=True — не уведомлять инициатора (используется для «Новый собеседник»).
    """
    user = await get_user(user_id)
    if not user:
        return

    companion_id = user.get("companion_id")

    # текущего переводим в меню
    await update_user_state(user_id, "menu")
    await update_user_companion(user_id, None)

    # собеседника тоже сбрасываем
    if companion_id:
        await update_user_state(companion_id, "menu")
        await update_user_companion(companion_id, None)

    # silent-режим → уведомляем только собеседника
    if silent:
        if companion_id:
            companion = await get_user(companion_id)
            if companion:
                await context.bot.send_message(
                    companion_id,
                    await tr(companion, "chat_ended_partner"),
                    reply_markup=await kb_main_menu(companion),
                )
        return

    # обычный выход → оба получают сообщение
    await context.bot.send_message(
        user_id,
        await tr(user, "chat_ended"),
        reply_markup=await kb_main_menu(user),
    )
    if companion_id:
        companion = await get_user(companion_id)
        if companion:
            await context.bot.send_message(
                companion_id,
                await tr(companion, "chat_ended_partner"),
                reply_markup=await kb_main_menu(companion),
            )
