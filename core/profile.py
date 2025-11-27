import html
from db.user_queries import get_user
from core.i18n import tr
from core.ranks import get_rank_by_minutes

async def send_profile(user_id: int, context):
    user = await get_user(user_id)
    if not user:
        return

    lang = user.get("lang", "en")
    nickname = user.get("nickname", "—")
    gender = user.get("gender", "—")
    total_minutes = user.get("total_minutes", 0)

    # ранги
    rank_key = get_rank_by_minutes(total_minutes)
    rank = await tr(user, rank_key)

    # пол
    gender_label = await tr(user, f"gender_{gender}") if gender else "—"

    text = (
        f"👤 <b>{html.escape(nickname)}</b>\n"
        f"🌐 {lang}\n"
        f"🚻 {gender_label}\n"
        f"⏳ {total_minutes} мин\n"
        f"🏆 {rank}"
    )

    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="HTML"
    )
