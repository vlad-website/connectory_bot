from db.user_queries import update_user_state, update_user_companion, get_user
from telegram import Bot
from collections import deque

queue = deque()

async def add_to_queue(user_id, theme, sub):
    user = await get_user(user_id)

    for other_id in list(queue):
        other = await get_user(other_id)

        if not other:
            continue

        same_theme = other["theme"] == theme
        sub_match = (
            sub == other["sub"] or
            sub == "Любая подтема" or
            other["sub"] == "Любая подтема"
        )

        if same_theme and sub_match:
            queue.remove(other_id)

            await update_user_state(user_id, "chatting")
            await update_user_state(other_id, "chatting")
            await update_user_companion(user_id, other_id)
            await update_user_companion(other_id, user_id)

            sub_a = sub if sub != "Любая подтема" else other["sub"]
            sub_b = other["sub"] if other["sub"] != "Любая подтема" else sub

            await Bot.get_current().send_message(user_id,
                f"🎉 Собеседник найден!\nТема: {theme}\nПодтема: {sub_a}"
            )
            await Bot.get_current().send_message(other_id,
                f"🎉 Собеседник найден!\nТема: {theme}\nПодтема: {sub_b}"
            )
            return

    queue.append(user_id)

async def is_in_chat(user_id):
    user = await get_user(user_id)
    return user and user.get("state") == "chatting"
