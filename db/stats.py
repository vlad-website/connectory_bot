from datetime import datetime, timedelta
from db.connection import get_db

async def get_stats():
    db = get_db()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    total_users = await db.users.count_documents({})
    new_users_week = await db.users.count_documents({"registered_at": {"$gte": week_ago}})
    searching_users = await db.users.count_documents({"state": "searching"})
    active_chats = await db.users.count_documents({"companion_id": {"$ne": None}})

    messages_total = await db.users.aggregate([
        {"$group": {"_id": None, "sum": {"$sum": "$messages_sent"}}}
    ]).to_list(length=1)

    messages_total = messages_total[0]["sum"] if messages_total else 0

    return {
        "total_users": total_users,
        "new_users_week": new_users_week,
        "searching_users": searching_users,
        "active_chats": active_chats,
        "messages_total": messages_total
    }
