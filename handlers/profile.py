from core.i18n import tr
from core.ranks import get_rank
from db.user_queries import get_total_minutes

async def build_profile_text(user: dict) -> str:
    """
    Создаёт текст профиля пользователя с i18n и рангами.
    """

    minutes = await get_total_minutes(user["id"])
    rank_key = get_rank(minutes)

    text = (
        f"👤 <b>{user.get('nickname')}</b>\n\n"
        f"⚧ <b>{await tr(user, 'choose_gender')}:</b> {await tr(user, user.get('gender'))}\n"
        f"🌐 <b>Язык:</b> {user.get('lang').upper()}\n"
        f"⏱ <b>Минут в диалогах:</b> {minutes}\n"
        f"🏅 <b>Ранг:</b> {await tr(user, rank_key)}"
    )

    return text
