# File: core/matchmaking.py
# -------------------------
from db.user_queries import update_user_state

queue = {}
active_chats = {}

async def find_match(user_id, theme):
    for uid, info in queue.items():
        if uid != user_id and info['theme'] == theme:
            # Remove both users from queue
            queue.pop(uid)
            queue.pop(user_id, None)
            # Save active chat
            active_chats[user_id] = uid
            active_chats[uid] = user_id
            return uid
    return None

async def add_to_queue(user_id, theme):
    queue[user_id] = {"theme": theme}
    await update_user_state(user_id, "searching")

async def end_chat(user_id):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        return partner_id
    return None

async def get_partner(user_id):
    return active_chats.get(user_id)
