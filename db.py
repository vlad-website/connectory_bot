# db.py
import asyncpg
import os
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")
pool = None

async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(DB_URL)
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    nickname TEXT,
                    gender TEXT,
                    state TEXT,
                    theme TEXT,
                    sub TEXT
                );
            """)
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.exception("❌ Failed to initialize DB: %s", e)

async def get_user(user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

async def create_user(user_id):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users (id, state) VALUES ($1, $2)", user_id, 'nickname')

async def update_user_state(user_id, state):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET state = $1 WHERE id = $2", state, user_id)

async def update_user_nickname(user_id, nickname):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET nickname = $1 WHERE id = $2", nickname, user_id)

async def update_user_gender(user_id, gender):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET gender = $1 WHERE id = $2", gender, user_id)

async def update_user_theme(user_id, theme):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET theme = $1 WHERE id = $2", theme, user_id)

async def update_user_sub(user_id, sub):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET sub = $1 WHERE id = $2", sub, user_id)
