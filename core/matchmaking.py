# core/matchmaking.py
import asyncio
import logging
from collections import deque
from typing import Deque, Dict

from db.user_queries import get_user, update_user_state, update_user_companion
from handlers.keyboards import kb_chat
from core.i18n import tr_lang

logger = logging.getLogger(__name__)

language_names = {
    "ru": "Русский", "uk": "Українська",
    "en": "English", "es": "Español",
    "fr": "Français", "de": "Deutsch",
}

queue: Deque[int] = deque()
active_search_tasks: Dict[int, asyncio.Task] = {}

async def add_to_queue(user_id: int, theme: str, sub: str, context):
    """
    Ставит пользователя в очередь или матчит. Любые исключения перехватываются внутри — наружу не выбрасываем.
    """
    try:
        user = await get_user(user_id)
        if not user:
            logger.debug("add_to_queue: user not found %s", user_id)
            return

        # ищем пару среди очереди
        for other_id in list(queue):
            if other_id == user_id:
                continue
            other = await get_user(other_id)
            if not other:
                continue

            same_theme = (other.get("theme") == theme)
            sub_match = (sub == other.get("sub") or sub == "any_sub" or other.get("sub") == "any_sub")
            if not (same_theme and sub_match):
                continue

            # удаляем обоих из очереди (если вдруг там есть)
            for qid in (other_id, user_id):
                try:
                    queue.remove(qid)
                except ValueError:
                    pass

            # ставим состояние чата
            await update_user_state(user_id, "chat")
            await update_user_state(other_id, "chat")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            # отменяем таймеры ретрая
            for qid in (user_id, other_id):
                t = active_search_tasks.pop(qid, None)
                if t and not t.done():
                    try:
                        t.cancel()
                    except Exception:
                        logger.exception("Failed to cancel retry task for %s", qid)

            # определяем локали/подтемы
            sub_a = sub if sub != "any_sub" else other.get("sub")
            sub_b = other.get("sub") if other.get("sub") != "any_sub" else sub

            lang_a = user.get("lang") or "en"
            lang_b = other.get("lang") or "en"

            # клавиатуры
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

            # безопасные переводы (tr_lang не должен падать)
            try:
                theme_a_local = tr_lang(lang_a, theme) or theme
                theme_b_local = tr_lang(lang_b, theme) or theme
                sub_a_local = tr_lang(lang_a, sub_a) or sub_a
                sub_b_local = tr_lang(lang_b, sub_b) or sub_b
                msg_a = tr_lang(
                    lang_a,
                    "found",
                    theme=theme_a_local,
                    sub=sub_a_local,
                    companion_lang=language_names.get(lang_b, lang_b),
                ) or "🎉 Собеседник найден!"
                msg_b = tr_lang(
                    lang_b,
                    "found",
                    theme=theme_b_local,
                    sub=sub_b_local,
                    companion_lang=language_names.get(lang_a, lang_a),
                ) or "🎉 Собеседник найден!"
            except Exception:
                logger.exception("tr_lang failed while building 'found' message")
                msg_a = "🎉 Собеседник найден!"
                msg_b = "🎉 Собеседник найден!"

            # отправляем found обоим (ошибки не пробрасываем)
            try:
                await context.bot.send_message(user_id, msg_a, reply_markup=markup_a)
            except Exception:
                logger.exception("Failed to send 'found' to %s", user_id)

            try:
                await context.bot.send_message(other_id, msg_b, reply_markup=markup_b)
            except Exception:
                logger.exception("Failed to send 'found' to %s", other_id)

            logger.info("Matched %s <-> %s (theme=%s sub=%s/%s)", user_id, other_id, theme, sub_a, sub_b)
            return

        # пары нет — ставим в очередь и запускаем ретрай
        if user_id not in queue:
            queue.append(user_id)
            task = asyncio.create_task(retry_search(user_id, theme, sub, context))
            active_search_tasks[user_id] = task

    except Exception:
        # Главное: наружу ошибку не отдаём
        logger.exception("add_to_queue crashed for user %s", user_id)
        # Ничего не возвращаем и не шлём сообщений — UI остаётся в состоянии "поиска"
