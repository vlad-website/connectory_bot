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
    """Убрать пользователя из очереди и отменить его таймер-ретрай, если он был."""
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
    """
    user = await get_user(user_id)
    if not user:
        logger.debug("add_to_queue: user not found %s", user_id)
        return

    # Пробуем найти пару
    for other_id in list(queue):
        if other_id == user_id:
            continue

        other = await get_user(other_id)
        if not other:
            try:
                queue.remove(other_id)
            except ValueError:
                pass
            continue

        same_theme = (other.get("theme") == theme)
        sub_match = (
            sub == other.get("sub")
            or sub == "any_sub"
            or other.get("sub") == "any_sub"
        )

        if same_theme and sub_match:
            # Нашли пару
            for uid in (user_id, other_id):
                try:
                    if uid in queue:
                        queue.remove(uid)
                except ValueError:
                    pass

            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # Останавливаем ретраи
            for uid in (user_id, other_id):
                task = active_search_tasks.pop(uid, None)
                if task and not task.done():
                    try:
                        task.cancel()
                    except Exception:
                        logger.exception("Failed to cancel retry task for %s", uid)

            # --- Безопасная сборка сообщений ---
            sub_a = sub if sub != "any_sub" else other.get("sub")
            sub_b = other.get("sub") if other.get("sub") != "any_sub" else sub

            lang_a = user.get("lang")
            lang_b = other.get("lang")

            # Перестрахуемся: перезапрашиваем свежие данные
            try:
                user = await get_user(user_id)
                other = await get_user(other_id)
            except Exception:
                logger.exception("Failed to refetch users after matching")

            # Клавиатуры
            try:
                markup_a = await kb_chat(user)
            except Exception:
                markup_a = None
                logger.exception("Failed to build chat keyboard for user %s", user_id)

            try:
                markup_b = await kb_chat(other)
            except Exception:
                markup_b = None
                logger.exception("Failed to build chat keyboard for user %s", other_id)

            # Безопасная локализация
            def safe_tr(lang, key, **kwargs):
                try:
                    return tr_lang(lang, key, **kwargs)
                except Exception:
                    logger.exception("tr_lang failed (%s, %s)", lang, key)
                    return None

            theme_a_local = safe_tr(lang_a, theme) or theme
            theme_b_local = safe_tr(lang_b, theme) or theme
            sub_a_local = safe_tr(lang_a, sub_a) or sub_a
            sub_b_local = safe_tr(lang_b, sub_b) or sub_b

            msg_a = safe_tr(
                lang_a,
                "found",
                theme=theme_a_local,
                sub=sub_a_local,
                companion_lang=language_names.get(lang_b, lang_b),
            )
            if not msg_a:
                msg_a = f"✅ Собеседник найден!\nТема: {theme_a_local}\nПодтема: {sub_a_local}"

            msg_b = safe_tr(
                lang_b,
                "found",
                theme=theme_b_local,
                sub=sub_b_local,
                companion_lang=language_names.get(lang_a, lang_a),
            )
            if not msg_b:
                msg_b = f"✅ Match found!\nTheme: {theme_b_local}\nSubtopic: {sub_b_local}"

            # Отправляем found
            try:
                await context.bot.send_message(user_id, msg_a, reply_markup=markup_a)
                logger.debug("Sent FOUND to %s with chat keyboard", user_id)
            except Exception:
                logger.exception("Failed to send found to %s", user_id)

            try:
                await context.bot.send_message(other_id, msg_b, reply_markup=markup_b)
                logger.debug("Sent FOUND to %s with chat keyboard", other_id)
            except Exception:
                logger.exception("Failed to send found to %s", other_id)

            logger.info(
                "Matched %s <-> %s (theme=%s sub=%s/%s)",
                user_id, other_id, theme, sub_a, sub_b,
            )
            return

    # Если не нашли пару — добавляем в очередь и ставим таймер
    if user_id not in queue:
        queue.append(user_id)

    if user_id not in active_search_tasks or active_search_tasks[user_id].done():
        task = asyncio.create_task(retry_search(user_id, theme, sub, context))
        active_search_tasks[user_id] = task


async def retry_search(user_id: int, theme: str, sub: str, context):
    """Повторный поиск через минуту."""
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

            await add_to_queue(user_id, theme, sub, context)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("retry_search failed for %s", user_id)


async def is_in_chat(user_id: int) -> bool:
    """Проверка: пользователь в активном чате?"""
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")
