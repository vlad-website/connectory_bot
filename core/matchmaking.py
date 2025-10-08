# core/matchmaking.py
import asyncio
import logging
from collections import deque
from typing import Deque, Dict

from db.user_queries import (
    get_user,
    update_user_state,
    update_user_companion,
)
from handlers.keyboards import kb_chat
from core.i18n import tr_lang            # синхронная функция локализации

logger = logging.getLogger(__name__)

# ---------- очередь поиска ----------
queue: Deque[int] = deque()
active_search_tasks: Dict[int, asyncio.Task] = {}

# ---------- убрать пользователя из очереди + отменить таску ----------
async def remove_from_queue(user_id: int):
    try:
        queue.remove(user_id)
    except ValueError:
        pass

    task = active_search_tasks.pop(user_id, None)
    if task and not task.done():
        try:
            task.cancel()
        except Exception:
            logger.exception("Failed to cancel search retry task for user %s", user_id)

# ---------- добавить в очередь / найти пару ----------
async def add_to_queue(user_id: int, theme: str, sub: str, context):
    """
    Добавляет пользователя в очередь и пытается найти пару.
    sub — ключ подтемы (например 'any_sub' или конкретный ключ из TOPICS).
    """
    user = await get_user(user_id)
    if not user:
        logger.debug("add_to_queue: user not found %s", user_id)
        return

    # пытаемся найти подходящего собеседника
    for other_id in list(queue):
        if other_id == user_id:
            continue
        other = await get_user(other_id)
        if not other:
            continue

        same_theme = (other.get("theme") == theme)
        # canonical check: 'any_sub' is the wildcard key stored in DB
        sub_match = (sub == other.get("sub") or sub == "any_sub" or other.get("sub") == "any_sub")

        if same_theme and sub_match:
            # удаляем найденного из очереди (и при необходимости - текущего)
            try:
                queue.remove(other_id)
            except ValueError:
                pass
            try:
                if user_id in queue:
                    queue.remove(user_id)
            except ValueError:
                pass

            # обновляем БД — ставим в чат и проставляем компаньонов
            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # Отменяем таймеры поиска (если были)
            t1 = active_search_tasks.pop(user_id, None)
            if t1 and not t1.done():
                try: t1.cancel()
                except Exception: logger.exception("Failed to cancel retry task for %s", user_id)
            t2 = active_search_tasks.pop(other_id, None)
            if t2 and not t2.done():
                try: t2.cancel()
                except Exception: logger.exception("Failed to cancel retry task for %s", other_id)

            # Формируем подписи под-тем (используем ключи, tr_lang их локализует)
            sub_a = sub if sub != "any_sub" else other.get("sub")
            sub_b = other.get("sub") if other.get("sub") != "any_sub" else sub

            lang_a = language_names.get(user.get("lang"), user.get("lang"))
            lang_b = language_names.get(other.get("lang"), other.get("lang"))

            # Подготовим клавиатуры — НЕ передаём coroutine в send_message
            try:
                markup_a = await kb_chat(user)    # правильно await + передаём user
            except Exception:
                logger.exception("Failed to build chat keyboard for user %s", user_id)
                markup_a = None

            try:
                markup_b = await kb_chat(other)
            except Exception:
                logger.exception("Failed to build chat keyboard for user %s", other_id)
                markup_b = None

            # Отправляем уведомления (локализуем tr_lang, он синхронный)
            msg_a = tr_lang(user.get("lang"), "found", theme=theme, sub=sub_a, lang=lang_b)
            msg_b = tr_lang(other.get("lang"), "found", theme=theme, sub=sub_b, lang=lang_a)

            try:
                await context.bot.send_message(user_id, msg_a, reply_markup=markup_a)
            except Exception:
                logger.exception("Failed to send 'found' message to %s", user_id)

            try:
                await context.bot.send_message(other_id, msg_b, reply_markup=markup_b)
            except Exception:
                logger.exception("Failed to send 'found' message to %s", other_id)

            logger.info("Matched %s <-> %s (theme=%s sub=%s/%s)", user_id, other_id, theme, sub_a, sub_b)
            return  # выход после удачного матча

    # если пары нет — ставим в очередь и запускаем таймер
    if user_id in queue:
        return

    queue.append(user_id)
    task = asyncio.create_task(retry_search(user_id, theme, sub, context))
    active_search_tasks[user_id] = task

# ---------- повторный поиск через 60 с ----------
async def retry_search(user_id: int, theme: str, sub: str, context):
    try:
        await asyncio.sleep(60)
        user = await get_user(user_id)
        if user and user.get("state") == "searching":
            try:
                await context.bot.send_message(user_id, tr_lang(user.get("lang"), "still_searching"))
            except Exception:
                logger.exception("Failed to send still_searching to %s", user_id)
            # повторяем попытку
            await add_to_queue(user_id, theme, sub, context)
    except asyncio.CancelledError:
        # нормальная отмена — ничего не логируем
        return
    except Exception:
        logger.exception("retry_search failed for %s", user_id)

# ---------- утилиты ----------
async def is_in_chat(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")
