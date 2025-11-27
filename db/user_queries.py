# db/user_queries.py
import logging
from datetime import datetime, timezone
from db.init_db import get_db

logger = logging.getLogger(__name__)

# ---------- helpers ----------
async def _exec(sql: str, *args):
    """Выполнить SQL и вернуть строку статуса."""
    pool = await get_db()
    async with pool.acquire() as conn:
        status = await conn.execute(sql, *args)
    logger.debug("SQL: %s  ARGS: %s → %s", sql, args, status)
    return status

# ---------- CRUD ----------
async def get_user(user_id: int) -> dict | None:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1::BIGINT",
            user_id
        )
        return dict(row) if row else None

async def create_user(user_id: int, lang: str = 'ru', nickname: str | None = None):
    user = await get_user(user_id)
    if user:
        logger.debug("create_user: user %s already exists, skipping", user_id)
        return
    try:
        status = await _exec(
            """
            INSERT INTO users (id, state, lang, nickname, registered_at, messages_sent, total_minutes)
            VALUES ($1::BIGINT, 'nickname', $2, $3, $4, 0, 0)
            """,
            user_id, lang, nickname, datetime.now(timezone.utc)
        )
        logger.debug("create_user %s → %s", user_id, status)
    except Exception:
        logger.exception("Failed to create_user %s", user_id)

# ---------- Updates ----------
async def update_user_state(user_id: int, state: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("state") == state:
            return
        await _exec("UPDATE users SET state = $1 WHERE id = $2::BIGINT", state, user_id)
    except Exception:
        logger.exception("Failed to update state for user %s", user_id)

async def update_user_nickname(user_id: int, nickname: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("nickname") == nickname:
            return
        await _exec("UPDATE users SET nickname = $1 WHERE id = $2::BIGINT", nickname, user_id)
    except Exception:
        logger.exception("Failed to update nickname for user %s", user_id)

async def update_user_gender(user_id: int, gender: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("gender") == gender:
            return
        await _exec("UPDATE users SET gender = $1 WHERE id = $2::BIGINT", gender, user_id)
    except Exception:
        logger.exception("Failed to update gender for user %s", user_id)

async def update_user_theme(user_id: int, theme: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("theme") == theme:
            return
        await _exec("UPDATE users SET theme = $1 WHERE id = $2::BIGINT", theme, user_id)
    except Exception:
        logger.exception("Failed to update theme for user %s", user_id)

async def update_user_sub(user_id: int, sub: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("sub") == sub:
            return
        await _exec("UPDATE users SET sub = $1 WHERE id = $2::BIGINT", sub, user_id)
    except Exception:
        logger.exception("Failed to update sub for user %s", user_id)

async def update_user_companion(user_id: int, companion_id: int | None):
    try:
        user = await get_user(user_id)
        if user and user.get("companion_id") == companion_id:
            return
        await _exec(
            "UPDATE users SET companion_id = $1::BIGINT WHERE id = $2::BIGINT",
            companion_id, user_id
        )
    except Exception:
        logger.exception("Failed to update companion for user %s", user_id)

async def update_user_lang(user_id: int, lang: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("lang") == lang:
            return
        await _exec("UPDATE users SET lang = $1 WHERE id = $2::BIGINT", lang, user_id)
    except Exception:
        logger.exception("Failed to update lang for user %s", user_id)

# ---------- Message counter ----------
async def increment_messages(user_id: int, count: int = 1):
    try:
        await _exec(
            "UPDATE users SET messages_sent = messages_sent + $1 WHERE id = $2::BIGINT",
            count, user_id
        )
    except Exception:
        logger.exception("Failed to increment messages for user %s", user_id)

# ---------- CHAT TIMER ----------
async def start_chat_timer(user_id: int):
    """Сохраняем время начала чата."""
    try:
        await _exec(
            "UPDATE users SET chat_started_at = $1 WHERE id = $2::BIGINT",
            datetime.now(timezone.utc), user_id
        )
        logger.debug("start_chat_timer %s", user_id)
    except Exception:
        logger.exception("Failed to start chat timer for user %s", user_id)


async def stop_chat_timer(user_id: int):
    """Считаем, сколько минут длился чат, добавляем к total_minutes."""
    try:
        user = await get_user(user_id)
        started = user.get("chat_started_at")

        if not started:
            return

        now = datetime.now(timezone.utc)
        diff_minutes = int((now - started).total_seconds() // 60)

        if diff_minutes < 1:
            diff_minutes = 1  # минимум 1 минута

        await _exec(
            """
            UPDATE users
            SET total_minutes = total_minutes + $1,
                chat_started_at = NULL
            WHERE id = $2::BIGINT
            """,
            diff_minutes, user_id
        )

        logger.debug("stop_chat_timer %s → +%s min", user_id, diff_minutes)

    except Exception:
        logger.exception("Failed to stop chat timer for user %s", user_id)


async def get_total_minutes(user_id: int) -> int:
    """Возвращает общее количество минут в чате."""
    try:
        user = await get_user(user_id)
        return int(user.get("total_minutes", 0))
    except Exception:
        logger.exception("Failed to get total minutes for user %s", user_id)
        return 0
