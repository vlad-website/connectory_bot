def get_rank(minutes: int) -> str:
    if minutes >= 480:
        return "rank_legend"
    elif minutes >= 240:
        return "rank_elite"
    elif minutes >= 120:
        return "rank_master"
    elif minutes >= 60:
        return "rank_pro"
    elif minutes >= 30:
        return "rank_talker"
    elif minutes >= 15:
        return "rank_active"
    elif minutes >= 5:
        return "rank_chatter"
    else:
        return "rank_newbie"
