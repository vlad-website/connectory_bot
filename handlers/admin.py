from db.stats import get_stats

async def send_admin_stats(update, context):
    stats = await get_stats()
    msg = (
        f"📊 *Статистика:*\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🆕 Новых за неделю: {stats['new_users_week']}\n"
        f"🔄 В поиске: {stats['searching_users']}\n"
        f"💬 Активных чатов: {stats['active_chats']}\n"
        f"✉️ Сообщений всего: {stats['messages_total']}\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
