def get_rank_by_minutes(minutes: int) -> str:
    if minutes < 10:
        return "rank_newbie"
    if minutes < 30:
        return "rank_talker"
    if minutes < 60:
        return "rank_chatter"
    if minutes < 120:
        return "rank_speaker"
    if minutes < 300:
        return "rank_communicator"
    if minutes < 600:
        return "rank_socializer"
    if minutes < 1200:
        return "rank_connector"
    if minutes < 2000:
        return "rank_conversationalist"
    return "rank_master"
