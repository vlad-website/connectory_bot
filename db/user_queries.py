# db/user_queries.py
import logging
from db.init_db import get_db

logger = logging.getLogger(__name__)

# ---------- helpers ----------
async def _exec(sql: str, *args):
    """Выполнить SQL и вернуть строку статуса, например 'UPDATE 1'."""
    pool = await get_db()
    async with pool.acquire() as conn:
        status = await conn.execute(sql, *args)
    print(f"SQL: {sql}  ARGS: {args}  →  {status}", flush=True)
    return status

# ---------- CRUD ----------
async def get_user(user_id: int) -> dict | None:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1::BIGINT", user_id)
        return dict(row) if row else None


async def create_user(user_id: int, lang: str = 'ru'):
    status = await _exec(
        "INSERT INTO users (id, state, lang) VALUES ($1::BIGINT, 'nickname', $2) ON CONFLICT DO NOTHING",
        user_id, lang,
    )
    logger.debug("create_user %s → %s", user_id, status)


async def update_user_state(user_id: int, state: str):
    status = await _exec(
        "UPDATE users SET state = $1 WHERE id = $2::BIGINT",
        state, user_id,
    )
    logger.debug("update_user_state %s → %s", user_id, status)


async def update_user_nickname(user_id: int, nickname: str):
    status = await _exec(
        "UPDATE users SET nickname = $1 WHERE id = $2::BIGINT",
        nickname, user_id,
    )
    logger.debug("update_user_nickname %s → %s", user_id, status)


async def update_user_gender(user_id: int, gender: str):
    status = await _exec(
        "UPDATE users SET gender = $1 WHERE id = $2::BIGINT",
        gender, user_id,
    )
    logger.debug("update_user_gender %s → %s", user_id, status)


async def update_user_theme(user_id: int, theme: str):
    status = await _exec(
        "UPDATE users SET theme = $1 WHERE id = $2::BIGINT",
        theme, user_id,
    )
    logger.debug("update_user_theme %s → %s", user_id, status)


async def update_user_sub(user_id: int, sub: str):
    status = await _exec(
        "UPDATE users SET sub = $1 WHERE id = $2::BIGINT",
        sub, user_id,
    )
    logger.debug("update_user_sub %s → %s", user_id, status)


async def update_user_companion(user_id: int, companion_id: int | None):
    """
    Сохраняем текущего собеседника.
    companion_id = None → очищаем связь.
    """
    status = await _exec(
        "UPDATE users SET companion_id = $1::BIGINT WHERE id = $2::BIGINT",
        companion_id, user_id,
    )
    logger.debug("update_user_companion %s → %s", user_id, status)

async def update_user_lang(user_id: int, lang: str):
    await _exec("UPDATE users SET lang = $1 WHERE id = $2::BIGINT", lang, user_id)
    
    logger.debug("update_user_lang %s → %s", user_id, status)
