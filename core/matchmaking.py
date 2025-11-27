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


from datetime import datetime

from db.user_queries import start_chat_timer, stop_chat_timer


logger = logging.getLogger(__name__)

# Читабельные названия языков для текста "собеседник найден"
LANGUAGE_NAMES = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

# Очередь и таймеры повторного поиска
queue: Deque[int] = deque()
active_search_tasks: Dict[int, asyncio.Task] = {}


async def remove_from_queue(user_id: int):
    """Убрать пользователя из очереди и отменить его ретрай-таймер (безопасно вызывать где угодно)."""
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


def _safe_tr(lang: str, key: str, **kwargs) -> str:
    """Безопасная локализация: если упало — вернуть ключ/аргумент как есть."""
    try:
        val = tr_lang(lang, key, **kwargs)
        if isinstance(val, str) and val.strip():
            return val
    except Exception:
        logger.exception("tr_lang failed: lang=%s key=%s", lang, key)
    # Фолбэк: если это тематический ключ — вернём его, если это текст found — соберём простую строку
    if key == "found":
        theme = kwargs.get("theme", "")
        sub = kwargs.get("sub", "")
        return f"✅ Match found!\nTheme: {theme}\nSubtopic: {sub}"
    return key


async def add_to_queue(user_id: int, theme: str, sub: str, context):
    """
    Поставить пользователя в очередь (предполагается, что state=searching уже выставлен),
    и попытаться сразу найти пару по теме и совместимой подтеме (учёт any_sub).
    """
    user = await get_user(user_id)
    if not user:
        logger.debug("add_to_queue: user not found %s", user_id)
        return

    # Пробуем найти пару среди уже ожидающих
    for other_id in list(queue):
        if other_id == user_id:
            continue

        other = await get_user(other_id)
        if not other:
            # мусор — удалим
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

        if not (same_theme and sub_match):
            continue

        # Нашли пару — подчистим очередь у обоих
        for uid in (user_id, other_id):
            try:
                if uid in queue:
                    queue.remove(uid)
            except ValueError:
                pass

        # Ставим обоим state=chatting и запоминаем companion
        await update_user_state(user_id, "chatting")
        await update_user_state(other_id, "chatting")
        now = datetime.utcnow()
        await set_chat_started(user_id, now)
        await set_chat_started(other_id, now)
        await update_user_companion(user_id, other_id)
        await update_user_companion(other_id, user_id)

        # Остановим их ретраи, если были
        for uid in (user_id, other_id):
            task = active_search_tasks.pop(uid, None)
            if task and not task.done():
                try:
                    task.cancel()
                except Exception:
                    logger.exception("Failed to cancel retry task for %s", uid)

        # Финальные подтемы с учётом any_sub
        sub_a = sub if sub != "any_sub" else other.get("sub")
        sub_b = other.get("sub") if other.get("sub") != "any_sub" else sub

        # На всякий случай перечитаем пользователей (могли измениться поля)
        try:
            user = await get_user(user_id)
            other = await get_user(other_id)
        except Exception:
            logger.exception("Failed to refetch users after matching")

        lang_a = (user or {}).get("lang") or "en"
        lang_b = (other or {}).get("lang") or "en"

        # Локализация темы/подтемы под язык каждого
        theme_a_local = _safe_tr(lang_a, theme)
        theme_b_local = _safe_tr(lang_b, theme)
        sub_a_local = _safe_tr(lang_a, sub_a) if sub_a else ""
        sub_b_local = _safe_tr(lang_b, sub_b) if sub_b else ""

        # Текст «собеседник найден» для каждого
        msg_a = _safe_tr(
            lang_a,
            "found",
            theme=theme_a_local,
            sub=sub_a_local,
            companion_lang=LANGUAGE_NAMES.get(lang_b, lang_b),
        )
        msg_b = _safe_tr(
            lang_b,
            "found",
            theme=theme_b_local,
            sub=sub_b_local,
            companion_lang=LANGUAGE_NAMES.get(lang_a, lang_a),
        )

        # Сборка клавиатур чата
        try:
            markup_a = await kb_chat(user)
        except Exception:
            markup_a = None
            logger.exception("Failed to build chat keyboard for %s", user_id)

        try:
            markup_b = await kb_chat(other)
        except Exception:
            markup_b = None
            logger.exception("Failed to build chat keyboard for %s", other_id)

        # Отправляем found обоим (ВАЖНО: именованные аргументы)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=msg_a,
                reply_markup=markup_a,
            )
            logger.debug("FOUND sent to %s", user_id)
        except Exception:
            logger.exception("Failed to send 'found' to %s", user_id)

        try:
            await context.bot.send_message(
                chat_id=other_id,
                text=msg_b,
                reply_markup=markup_b,
            )
            logger.debug("FOUND sent to %s", other_id)
        except Exception:
            logger.exception("Failed to send 'found' to %s", other_id)

        logger.info(
            "Matched %s <-> %s (theme=%s sub=%s/%s)",
            user_id, other_id, theme, sub_a, sub_b,
        )
        return

    # Пару не нашли — добавим в очередь и поставим таймер на повтор
    if user_id not in queue:
        queue.append(user_id)

    # Не дублируем таймер
    if user_id not in active_search_tasks or active_search_tasks[user_id].done():
        task = asyncio.create_task(retry_search(user_id, theme, sub, context))
        active_search_tasks[user_id] = task


async def retry_search(user_id: int, theme: str, sub: str, context):
    """
    Через минуту напоминаем про поиск и пытаемся ещё раз.
    Отменяется, если пользователь уже вышел из поиска или сматчился.
    """
    try:
        await asyncio.sleep(60)
        user = await get_user(user_id)
        if user and user.get("state") == "searching":
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=_safe_tr(user.get("lang") or "en", "still_searching"),
                )
            except Exception:
                logger.exception("Failed to send still_searching to %s", user_id)

            await add_to_queue(user_id, theme, sub, context)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("retry_search failed for %s", user_id)


async def is_in_chat(user_id: int) -> bool:
    """Проверка: пользователь уже в активном чате?"""
    user = await get_user(user_id)
    return bool(user and user.get("state") == "chatting")
