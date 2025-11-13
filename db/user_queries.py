# db/user_queries.py
import logging
from datetime import datetime
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
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1::BIGINT", user_id)
        return dict(row) if row else None

async def create_user(user_id: int, lang: str = 'ru', nickname: str | None = None):
    """
    Создаём нового пользователя. Добавляем дату регистрации и счётчик сообщений.
    """
    try:
        status = await _exec(
            """
            INSERT INTO users (id, state, lang, nickname, registered_at, messages_sent)
            VALUES ($1::BIGINT, 'nickname', $2, $3, $4, 0)
            ON CONFLICT (id) DO NOTHING
            """,
            user_id, lang, nickname, datetime.utcnow()
        )
        logger.debug("create_user %s → %s", user_id, status)
    except Exception:
        logger.exception("Failed to create_user %s", user_id)

# ---------- Updates ----------
async def update_user_state(user_id: int, state: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("state") == state:
            logger.debug("State for user %s is already %s, skipping update", user_id, state)
            return
        await _exec("UPDATE users SET state = $1 WHERE id = $2::BIGINT", state, user_id)
        logger.debug("update_user_state %s → %s", user_id, state)
    except Exception:
        logger.exception("Failed to update state for user %s", user_id)

async def update_user_nickname(user_id: int, nickname: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("nickname") == nickname:
            logger.debug("Nickname for user %s is already %s, skipping update", user_id, nickname)
            return
        await _exec("UPDATE users SET nickname = $1 WHERE id = $2::BIGINT", nickname, user_id)
        logger.debug("update_user_nickname %s → %s", user_id, nickname)
    except Exception:
        logger.exception("Failed to update nickname for user %s", user_id)

async def update_user_gender(user_id: int, gender: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("gender") == gender:
            logger.debug("Gender for user %s is already %s, skipping update", user_id, gender)
            return
        await _exec("UPDATE users SET gender = $1 WHERE id = $2::BIGINT", gender, user_id)
        logger.debug("update_user_gender %s → %s", user_id, gender)
    except Exception:
        logger.exception("Failed to update gender for user %s", user_id)

async def update_user_theme(user_id: int, theme: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("theme") == theme:
            logger.debug("Theme for user %s is already %s, skipping update", user_id, theme)
            return
        await _exec("UPDATE users SET theme = $1 WHERE id = $2::BIGINT", theme, user_id)
        logger.debug("update_user_theme %s → %s", user_id, theme)
    except Exception:
        logger.exception("Failed to update theme for user %s", user_id)

async def update_user_sub(user_id: int, sub: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("sub") == sub:
            logger.debug("Sub for user %s is already %s, skipping update", user_id, sub)
            return
        await _exec("UPDATE users SET sub = $1 WHERE id = $2::BIGINT", sub, user_id)
        logger.debug("update_user_sub %s → %s", user_id, sub)
    except Exception:
        logger.exception("Failed to update sub for user %s", user_id)

async def update_user_companion(user_id: int, companion_id: int | None):
    try:
        user = await get_user(user_id)
        if user and user.get("companion_id") == companion_id:
            logger.debug("Companion for user %s is already %s, skipping update", user_id, companion_id)
            return
        await _exec(
            "UPDATE users SET companion_id = $1::BIGINT WHERE id = $2::BIGINT",
            companion_id, user_id
        )
        logger.debug("update_user_companion %s → %s", user_id, companion_id)
    except Exception:
        logger.exception("Failed to update companion for user %s", user_id)

async def update_user_lang(user_id: int, lang: str):
    try:
        user = await get_user(user_id)
        if not user or user.get("lang") == lang:
            logger.debug("Lang for user %s is already %s, skipping update", user_id, lang)
            return
        await _exec("UPDATE users SET lang = $1 WHERE id = $2::BIGINT", lang, user_id)
        logger.debug("update_user_lang %s → %s", user_id, lang)
    except Exception:
        logger.exception("Failed to update lang for user %s", user_id)

# ---------- Message counter ----------
async def increment_messages(user_id: int, count: int = 1):
    try:
        await _exec(
            "UPDATE users SET messages_sent = messages_sent + $1 WHERE id = $2::BIGINT",
            count, user_id
        )
        logger.debug("increment_messages %s → +%s", user_id, count)
    except Exception:
        logger.exception("Failed to increment messages for user %s", user_id)


