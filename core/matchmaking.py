import asyncio
from collections import deque

from db.user_queries import (
    get_user,
    update_user_state,
    update_user_companion,
)
from handlers.keyboards import kb_chat
from core.i18n import tr_lang            # локализация строк

# Человекочитаемые названия языков
language_names = {
    "ru": "Русский",     "uk": "Українська",
    "en": "English",     "es": "Español",
    "fr": "Français",    "de": "Deutsch",
}

# ---------- очередь поиска ----------
queue: deque[int] = deque()
active_search_tasks: dict[int, asyncio.Task] = {}

# ---------- добавить в очередь / найти пару ----------
async def add_to_queue(user_id: int, theme: str, sub: str, context):
    user = await get_user(user_id)

    # ❶ Пытаемся найти подходящего собеседника
    for other_id in list(queue):
        other = await get_user(other_id)
        if not other:
            continue
        if other_id == user_id:
            continue  # нельзя матчить самого себя

        same_theme = other["theme"] == theme
        sub_match = (
            sub == other["sub"] or
            sub == "Любая подтема" or
            other["sub"] == "Любая подтема"
        )

        if same_theme and sub_match:
            queue.remove(other_id)                      # убираем из очереди

            # ❷ Обоих переводим в state = chatting
            await update_user_state(user_id,  "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id,  other_id)
            await update_user_companion(other_id, user_id)

            # ❸ Формируем подписи под‑тем
            sub_a = sub if sub != "Любая подтема" else other["sub"]
            sub_b = other["sub"] if other["sub"] != "Любая подтема" else sub

            # ❹ Локализованный вывод
            lang_a = language_names.get(user["lang"],  user["lang"])
            lang_b = language_names.get(other["lang"], other["lang"])

            await context.bot.send_message(
                user_id,
                tr_lang(
                    user["lang"], "found",
                    theme=theme, sub=sub_a, lang=lang_b
                ),
                reply_markup=kb_chat()
            )
            await context.bot.send_message(
                other_id,
                tr_lang(
                    other["lang"], "found",
                    theme=theme, sub=sub_b, lang=lang_a
                ),
                reply_markup=kb_chat()
            )
            return                              # важен выход после успеха

    if user_id in queue:
        return  # уже в очереди
    # ❺ Пары нет — ставим в очередь и запускаем таймер
    queue.append(user_id)
    task = asyncio.create_task(retry_search(user_id, theme, sub, context))
    active_search_tasks[user_id] = task

# ---------- повторный поиск через 60 с ----------
async def retry_search(user_id: int, theme: str, sub: str, context):
    await asyncio.sleep(60)
    user = await get_user(user_id)
    if user and user["state"] == "searching":
        await context.bot.send_message(
            user_id,
            "⏳ Всё ещё ищем собеседника... Попробуем ещё раз."
        )
        await add_to_queue(user_id, theme, sub, context)

# ---------- утилиты ----------
async def is_in_chat(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")

async def remove_from_queue(user_id: int):
    """Убираем пользователя из очереди, если он там есть."""
    try:
        queue.remove(user_id)
    except ValueError:
        pass
