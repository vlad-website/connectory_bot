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

# Понятные подписи языков для сообщений "собеседник найден"
language_names = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

# Очередь и активные задачи ретрая
queue: Deque[int] = deque()
active_search_tasks: Dict[int, asyncio.Task] = {}


async def remove_from_queue(user_id: int):
    """
    Убрать пользователя из очереди и отменить его таймер-ретрай, если он был.
    Безопасно для вызова в любом состоянии.
    """
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
            logger.exception("Failed to cancel search task for %s", user_id)


async def add_to_queue(user_id: int, theme: str, sub: str, context):
    """
    Поставить пользователя в очередь (state=searching должен быть уже установлен)
    и попытаться сразу найти пару по той же теме и совместимой подтеме.
    sub — ключ ('any_sub' или конкретный ключ из TOPICS).
    """
    user = await get_user(user_id)
    if not user:
        logger.debug("add_to_queue: user not found %s", user_id)
        return

    # Пробуем найти пару среди ожидающих
    for other_id in list(queue):
        if other_id == user_id:
            continue

        other = await get_user(other_id)
        if not other:
            # мусор в очереди
            try:
                queue.remove(other_id)
            except ValueError:
                pass
            continue

        # Совпадение темы
        same_theme = (other.get("theme") == theme)

        # Совместимость подтем (учёт any_sub)
        sub_match = (
            sub == other.get("sub")
            or sub == "any_sub"
            or other.get("sub") == "any_sub"
        )

        if same_theme and sub_match:
            # Удаляем из очереди обоих, если там есть
            for uid in (user_id, other_id):
                try:
                    if uid in queue:
                        queue.remove(uid)
                except ValueError:
                    pass

            # Ставим обоим state=chatting и запоминаем companion_id
            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # Останавливаем активные ретраи
            for uid in (user_id, other_id):
                task = active_search_tasks.pop(uid, None)
                if task and not task.done():
                    try:
                        task.cancel()
                    except Exception:
                        logger.exception("Failed to cancel retry task for %s", uid)

            # Финальные ключи подтем (подставим конкретную, если у кого-то any_sub)
            sub_a = sub if sub != "any_sub" else other.get("sub")
            sub_b = other.get("sub") if other.get("sub") != "any_sub" else sub

            # Языки пользователей
            lang_a = user.get("lang")
            lang_b = other.get("lang")

            # Строим клавиатуры чата
            try:
                markup_a = await kb_chat(user)
            except Exception:
                logger.exception("Failed to build chat keyboard for user %s", user_id)
                markup_a = None

            try:
                markup_b = await kb_chat(other)
            except Exception:
                logger.exception("Failed to build chat keyboard for user %s", other_id)
                markup_b = None

            # Локализуем тему/подтему под язык каждого пользователя
            theme_a_local = tr_lang(lang_a, theme)
            theme_b_local = tr_lang(lang_b, theme)
            sub_a_local = tr_lang(lang_a, sub_a)
            sub_b_local = tr_lang(lang_b, sub_b)

            # Сообщения "собеседник найден" на языках каждого
            msg_a = tr_lang(
                lang_a,
                "found",
                theme=theme_a_local,
                sub=sub_a_local,
                companion_lang=language_names.get(lang_b, lang_b),
            )
            msg_b = tr_lang(
                lang_b,
                "found",
                theme=theme_b_local,
                sub=sub_b_local,
                companion_lang=language_names.get(lang_a, lang_a),
            )

            # Отправляем
            try:
                await context.bot.send_message(user_id, msg_a, reply_markup=markup_a)
            except Exception:
                logger.exception("Failed to send 'found' to %s", user_id)

            try:
                await context.bot.send_message(other_id, msg_b, reply_markup=markup_b)
            except Exception:
                logger.exception("Failed to send 'found' to %s", other_id)

            logger.info(
                "Matched %s <-> %s (theme=%s sub=%s/%s)",
                user_id,
                other_id,
                theme,
                sub_a,
                sub_b,
            )
            return

    # Пары не нашли: ставим в очередь и запускаем отложенную проверку
    if user_id not in queue:
        queue.append(user_id)

    # Если ретрай уже есть — не создаём второй
    if user_id not in active_search_tasks or active_search_tasks[user_id].done():
        task = asyncio.create_task(retry_search(user_id, theme, sub, context))
        active_search_tasks[user_id] = task


async def retry_search(user_id: int, theme: str, sub: str, context):
    """
    Через паузу напоминает пользователю, что поиск идёт, и пробует матч ещё раз.
    Отменяется, если найден собеседник или пользователь покидает очередь.
    """
    try:
        await asyncio.sleep(60)
        user = await get_user(user_id)
        if user and user.get("state") == "searching":
            try:
                await context.bot.send_message(
                    user_id,
                    tr_lang(user.get("lang"), "still_searching"),
                )
            except Exception:
                logger.exception("Failed to send still_searching to %s", user_id)

            # Повторная попытка поиска
            await add_to_queue(user_id, theme, sub, context)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("retry_search failed for %s", user_id)


async def is_in_chat(user_id: int) -> bool:
    """Хелпер: пользователь в активном чате?"""
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")
