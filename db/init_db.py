import asyncpg
import logging
from config import DATABASE_URL

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
                    sub TEXT,
                    companion_id BIGINT
                );
            """)

            # На случай, если какие-то поля не добавились ранее — добавим безопасно
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS companion_id BIGINT;")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname TEXT;")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS state TEXT;")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS theme TEXT;")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub TEXT;")

        logger.info("✅ Database initialized")
    except Exception as e:
        logger.exception("❌ Failed to initialize database")

async def get_db():
    global pool
    return pool
