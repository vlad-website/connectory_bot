# Folder: db/user_queries.py
# -------------------------
from db.init_db import get_db

async def get_user(user_id):
    pool = await get_db()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

async def create_user(user_id):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users (id, state) VALUES ($1, 'nickname')", user_id)

async def update_user_state(user_id, state):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET state = $1 WHERE id = $2", state, user_id)

async def update_user_nickname(user_id, nickname):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET nickname = $1 WHERE id = $2", nickname, user_id)

async def update_user_gender(user_id, gender):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET gender = $1 WHERE id = $2", gender, user_id)

async def update_user_theme(user_id, theme):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET theme = $1 WHERE id = $2", theme, user_id)

async def update_user_sub(user_id, sub):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET sub = $1 WHERE id = $2", sub, user_id)

