# Folder: db/init_db.py
# -------------------------
import asyncpg
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)
pool = None

async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
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
        logger.info("✅ DB initialized")
    except Exception as e:
        logger.exception("❌ DB init failed: %s", e)

async def get_db():
    global pool
    return pool

