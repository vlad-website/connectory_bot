from datetime import datetime, timedelta
from init_db import get_db  # <-- здесь используем твой файл с asyncpg

async def get_stats():
    pool = await get_db()

    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users;")
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users_week = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE registered_at >= $1;", week_ago
        )
        searching_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE state = 'searching';"
        )
        active_chats = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE companion_id IS NOT NULL;"
        )
        messages_total = await conn.fetchval(
            "SELECT SUM(messages_sent) FROM users;"
        )

    return {
        "total_users": total_users,
        "new_users_week": new_users_week,
        "searching_users": searching_users,
        "active_chats": active_chats,
        "messages_total": messages_total or 0
    }
