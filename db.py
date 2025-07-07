import asyncpg
import os

DB_URL = os.getenv("DATABASE_URL")

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                nickname TEXT,
                gender TEXT,
                state TEXT,
                language TEXT DEFAULT 'ru',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

async def get_user(user_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def create_user(user_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )

async def update_user_state(user_id, state):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET state = $1 WHERE user_id = $2", state, user_id)

async def update_user_nickname(user_id, nickname):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET nickname = $1 WHERE user_id = $2", nickname, user_id)

async def update_user_gender(user_id, gender):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET gender = $1 WHERE user_id = $2", gender, user_id)
