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
from core.i18n import tr_lang

logger = logging.getLogger(__name__)

# Понятные имена языков (для вставки в сообщение)
language_names = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

queue: Deque[int] = deque()               # пользователи в поиске
active_search_tasks: Dict[int, asyncio.Task] = {}  # таймеры повторного поиска


async def remove_from_queue(user_id: int):
    """Безопасно убрать пользователя из очереди и отменить task ретрая."""
    try:
        if user_id in queue:
            queue.remove(user_id)
    except ValueError:
        pass

    task = active_search_tasks.pop(user_id, None)
    if task and not task.done():
        try:
            task.cancel()
        except Exception:
            logger.exception("Failed to cancel search task for user %s", user_id)


async def add_to_queue(user_id: int, theme: str, sub: str, context):
    """Добавление пользователя в очередь и попытка найти пару."""
    user = await get_user(user_id)
    if not user:
        logger.debug("add_to_queue: user not found %s", user_id)
        return

    # Ищем подходящего пользователя
    for other_id in list(queue):
        if other_id == user_id:
            continue

        other = await get_user(other_id)
        if not other:
            queue.remove(other_id)
            continue

        # ✅ Совпадение тем и совместимость подтем
        same_theme = other.get("theme") == theme
        sub_match = (
            sub == other.get("sub")
            or sub == "any_sub"
            or other.get("sub") == "any_sub"
        )

        if same_theme and sub_match:
            # ❗ ВАЖНО: убираем из очереди до обновления state
            for uid in (user_id, other_id):
                try:
                    queue.remove(uid)
                except ValueError:
                    pass

            # обновляем state и companion для обоих
            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")

            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # Останавливаем таймеры retry
            for uid in (user_id, other_id):
                task = active_search_tasks.pop(uid, None)
                if task and not task.done():
                    task.cancel()

            # определяем финальную подтему
            sub_user = sub if sub != "any_sub" else other.get("sub")
            sub_other = other.get("sub") if other.get("sub") != "any_sub" else sub

            lang_user = user.get("lang")
            lang_other = other.get("lang")

            # локализация темы/подтем
            def safe_localize(lang, key):
                try:
                    return tr_lang(lang, key)
                except Exception:
                    return key

            theme_u = safe_localize(lang_user, theme)
            theme_o = safe_localize(lang_other, theme)

            sub_u = safe_localize(lang_user, sub_user)
            sub_o = safe_localize(lang_other, sub_other)

            # ✅ формируем два разных сообщения (ВАЖНО!)
            msg_user = tr_lang(
                lang_user,
                "found",
                theme=theme_u,
                sub=sub_u,
                companion_lang=language_names.get(lang_other, lang_other)
            )

            msg_other = tr_lang(
                lang_other,
                "found",
                theme=theme_o,
                sub=sub_o,
                companion_lang=language_names.get(lang_user, lang_user)
            )

            # клавиатуры
            markup_user = await kb_chat(user)
            markup_other = await kb_chat(other)

            # отправляем каждому на его языке
            await context.bot.send_message(
            chat_id=user_id,
            text=msg_user,
            reply_markup=markup_user,
            )
            
            await context.bot.send_message(
                chat_id=other_id,
                text=msg_other,
                reply_markup=markup_other,
            )

            logger.info(
                "🎯 MATCH: %s (%s) ↔ %s (%s) | theme=%s sub=%s/%s",
                user_id, lang_user, other_id, lang_other,
                theme, sub_user, sub_other
            )

            return

    # Пары не нашли → добавляем в очередь
    if user_id not in queue:
        queue.append(user_id)

    # запускаем таймер напоминания (1 retry = 60 сек)
    if user_id not in active_search_tasks or active_search_tasks[user_id].done():
        task = asyncio.create_task(retry_search(user_id, theme, sub, context))
        active_search_tasks[user_id] = task


async def retry_search(user_id: int, theme: str, sub: str, context):
    """через минуту напоминаем пользователю и ищем повторно."""
    try:
        await asyncio.sleep(60)

        user = await get_user(user_id)
        if not user or user.get("state") != "searching":
            return

        await context.bot.send_message(
            user_id,
            tr_lang(user.get("lang"), "still_searching")
        )

        await add_to_queue(user_id, theme, sub, context)

    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("retry_search failed for %s", user_id)


async def is_in_chat(user_id: int) -> bool:
    """true если пользователь в активном чате"""
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")
