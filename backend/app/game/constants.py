"""游戏常量：板子、角色、阶段。"""

ROLE_LABELS = {
    "wolf": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "guard": "守卫",
    "villager": "平民",
}

GOOD_ROLES = {"seer", "witch", "hunter", "guard", "villager"}
SPECIAL_ROLES = {"seer", "witch", "hunter", "guard"}  # 神职
WOLF_ROLES = {"wolf"}

# 板子：6人（无警长）/ 9人（警长）/ 12人（警长）
BOARDS = {
    6: ["wolf", "wolf", "seer", "witch", "villager", "villager"],
    9: ["wolf", "wolf", "wolf", "seer", "witch", "hunter", "villager", "villager", "villager"],
    12: ["wolf", "wolf", "wolf", "wolf", "seer", "witch", "hunter", "guard", "villager", "villager", "villager", "villager"],
}


def role_setup_for(board_size: int) -> list[dict[str, int | str]]:
    """返回公开的角色构成，不包含任何座位分配信息。"""
    board = BOARDS.get(board_size, [])
    setup: list[dict[str, int | str]] = []
    seen: set[str] = set()
    for role in board:
        if role in seen:
            continue
        seen.add(role)
        setup.append({"role": role, "label": ROLE_LABELS[role], "count": board.count(role)})
    return setup


SHERIFF_BOARDS = {9, 12}

PHASE_LABELS = {
    "lobby": "房间准备",
    "night": "夜晚",
    "sheriff_election": "警长竞选",
    "night_result": "公布夜间结果",
    "day_speech": "白天发言",
    "lynch_vote": "放逐投票",
    "lynch_pk_speech": "平票PK发言",
    "lynch_pk_vote": "平票PK投票",
    "hunter_shot": "猎人开枪",
    "sheriff_transfer": "警徽移交",
    "last_words": "遗言",
    "ended": "对局结束",
}

# 窗口类型（当前需要谁行动、做什么）
WINDOW_LABELS = {
    "speech": "发言",
    "election_apply": "上警",
    "election_speak": "警上发言",
    "election_vote": "警长投票",
    "election_pk_speak": "警长PK发言",
    "election_pk_vote": "警长PK投票",
    "lynch_vote": "放逐投票",
    "lynch_pk_speak": "PK发言",
    "lynch_pk_vote": "PK投票",
    "wolf_kill": "狼人杀人",
    "night_skill": "夜间技能",
    "hunter_shot": "猎人开枪",
    "sheriff_transfer": "警徽移交",
    "last_words": "遗言",
    "wolf_chat": "狼人私聊",
}

# 角色死亡模式
DEATH_MODES = {
    "wolf": "被狼人击杀",
    "poison": "被女巫毒杀",
    "lynch": "被放逐",
    "explode": "自爆",
    "hunter": "被猎人开枪",
}

WINNER_LABELS = {"good": "好人阵营", "wolf": "狼人阵营"}
