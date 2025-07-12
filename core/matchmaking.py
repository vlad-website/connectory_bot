import asyncio
from collections import deque
from telegram import Bot

from db.user_queries import (
    update_user_state, update_user_companion, get_user
)
from handlers.keyboards import kb_chat

queue = deque()               # <— объявляем очередь
active_search_tasks = {}

async def add_to_queue(user_id: int, theme: str, sub: str):
    """Добавить пользователя в очередь и попробовать найти пару."""
    user = await get_user(user_id)

    # пытаемся найти совместимого собеседника
    for other_id in list(queue):
        other = await get_user(other_id)
        if not other:
            continue

        same_theme = other["theme"] == theme
        sub_match = (
            sub == other["sub"] or
            sub == "Любая подтема" or
            other["sub"] == "Любая подтема"
        )

        if same_theme and sub_match:
            queue.remove(other_id)

            # переводим обоих в состояние 'chatting'
            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # формируем подпись для каждого
            sub_a = sub if sub != "Любая подтема" else other["sub"]
            sub_b = other["sub"] if other["sub"] != "Любая подтема" else sub

            # отправляем обоим сообщение и клавиатуру чата
            await Bot.get_current().send_message(
                user_id,
                f"🎉 Собеседник найден!\nТема: {theme}\nПодтема: {sub_a}",
                reply_markup=kb_chat()
            )
            await Bot.get_current().send_message(
                other_id,
                f"🎉 Собеседник найден!\nТема: {theme}\nПодтема: {sub_b}",
                reply_markup=kb_chat()
            )
            return

    # пока пары нет — ставим в очередь
    queue.append(user_id)

    # таймер повторного поиска
    task = asyncio.create_task(retry_search(user_id, theme, sub))
    active_search_tasks[user_id] = task

async def retry_search(user_id: int, theme: str, sub: str):
    """Через минуту повторно пытаемся найти пару."""
    await asyncio.sleep(60)
    user = await get_user(user_id)
    if user and user["state"] == "searching":
        await Bot.get_current().send_message(
            user_id,
            "⏳ Всё ещё ищем собеседника... Попробуем ещё раз."
        )
        await add_to_queue(user_id, theme, sub)

async def is_in_chat(user_id: int) -> bool:
    user = await get_user(user_id)
    return user and user.get("state") == "chatting"

async def remove_from_queue(user_id: int):
    """Убираем пользователя из очереди, если он там есть."""
    try:
        queue.remove(user_id)
    except ValueError:
        pass
