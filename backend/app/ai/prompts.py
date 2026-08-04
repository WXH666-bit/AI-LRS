"""AI 玩家提示词构建。严格按座位可见信息生成，禁止泄漏隐藏信息。"""
from ..game.constants import DEATH_MODES, PHASE_LABELS, ROLE_LABELS, WINDOW_LABELS
from ..game.engine import SPEECH_WINDOWS, VOTE_WINDOWS
from ..models import AIPersona
from .adapters import parse_ai_json  # noqa: F401


def _phase_event_line(ev: dict) -> str | None:
    """把事件格式化为一行中文文本（仅公开或本座位可见的事件）。"""
    t, pl = ev["type"], ev["payload"]
    actor = ev["actor_seat"]
    night = ev["night"]
    day = ev["day"]

    if t == "game_started":
        return f"游戏开始（{pl['board_size']}人局）"
    if t == "phase_change":
        phase = pl.get("phase", "")
        prefix = f"第{pl.get('night', 0)}夜" if phase == "night" else f"第{pl.get('day', 0)}天"
        return f"—— {prefix}·{PHASE_LABELS.get(phase, phase)} ——"
    if t == "speech":
        if pl.get("skipped"):
            return f"{actor}号跳过发言"
        return f"{actor}号发言：{pl.get('text', '')}"
    if t in ("vote", "pk_vote"):
        return f"{actor}号投票→{pl.get('target')}号" if pl.get("target") else f"{actor}号弃权"
    if t in ("election_vote", "election_pk_vote"):
        return f"{actor}号投警长票→{pl.get('target')}号" if pl.get("target") else f"{actor}号弃权"
    if t == "wolf_chat":
        return f"【狼人私聊】{actor}号：{pl.get('text', '')}"
    if t == "wolf_vote":
        return f"{actor}号狼选择击杀{pl.get('target')}号" if pl.get("target") else f"{actor}号狼选择空刀"
    if t == "wolf_kill_result":
        return f"狼人击杀目标：{pl.get('target')}号" if pl.get("target") else "狼人本夜空刀"
    if t == "guard_action":
        return f"你（守卫）守护了{pl.get('target')}号" if pl.get("target") else "你（守卫）选择不守护"
    if t == "seer_result":
        if pl.get("target") is None:
            return "你（预言家）选择不查验"
        label = "狼人" if pl.get("result") == "wolf" else "好人"
        return f"你（预言家）查验了{pl.get('target')}号：{label}"
    if t == "witch_info":
        return f"你（女巫）得知今夜被狼人袭击的是{pl.get('victim')}号" if pl.get("victim") is not None else "你（女巫）得知今夜无人被狼人袭击"
    if t == "witch_action":
        a = pl.get("action")
        if a == "save":
            return f"你（女巫）使用解药救了{pl.get('target')}号"
        if a == "poison":
            return f"你（女巫）使用毒药毒了{pl.get('target')}号"
        return "你（女巫）选择不用药"
    if t == "night_result":
        if pl.get("peaceful"):
            return "昨夜平安"
        parts = [f"{d['seat']}号{DEATH_MODES.get(d['mode'], '死亡')}" for d in pl.get("deaths", [])]
        return "昨夜出局：" + "、".join(parts)
    if t == "hunter_shot":
        if pl.get("target"):
            return f"{actor}号猎人开枪带走了{pl.get('target')}号"
        return f"{actor}号猎人选择不开枪"
    if t == "lynch_result":
        if pl.get("seat"):
            return f"放逐投票：{pl.get('seat')}号被放逐"
        return "放逐投票：无人被放逐"
    if t == "wolf_explode":
        return f"{actor}号狼人自爆"
    if t == "sheriff_apply":
        return f"{actor}号上警"
    if t == "sheriff_withdraw":
        return f"{actor}号退水"
    if t == "sheriff_pass":
        return f"{actor}号不上警"
    if t == "sheriff_elected":
        return f"{pl.get('seat')}号当选警长"
    if t == "sheriff_transfer":
        return f"警长将警徽移交给{pl.get('target')}号"
    if t == "sheriff_destroy":
        return "警长撕毁警徽"
    if t == "seat_control":
        c = "人类接管" if pl.get("controller_type") == "human" else "AI托管"
        return f"{actor}号转为{c}"
    if t == "game_over":
        label = "好人阵营" if pl.get("winner") == "good" else "狼人阵营"
        return f"游戏结束：{label}获胜（{pl.get('reason', '')}）"
    if t == "last_words":
        if pl.get("skipped"):
            return f"{actor}号遗言（跳过）"
        return f"{actor}号遗言：{pl.get('text', '')}"
    return None


def format_history(engine, seat: int, limit: int = 80) -> str:
    """本座位可见的事件流（公开 + 私有）。"""
    lines: list[str] = []
    for ev in engine.events[-limit:]:
        vis = ev.get("visible_to")
        if vis is not None and seat not in vis:
            continue
        line = _phase_event_line(ev)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _rules_text(board_size: int) -> str:
    sheriff = "（本局启用警长）" if board_size in (9, 12) else "（本局不启用警长）"
    return f"""狼人杀规则（{board_size}人局）：
- 阵营：好人阵营（预言家、女巫、猎人、守卫、平民）与狼人阵营。
- 胜利条件：好人消灭全部狼人获胜；狼人消灭全部平民或全部神职（预言家/女巫/猎人/守卫）获胜。
- 夜晚：狼人共同决定击杀目标，票数并列时本夜空刀；狼人之间有私聊频道。守卫每夜守护一人，不能连续两晚守护同一人。预言家每夜查验一名玩家，结果只有“好人/狼人”。女巫有解药和毒药各一瓶，整局各一次，首夜可以自救，同一夜不能同时使用两瓶药；被狼人袭击的目标如果同时被守卫守护并被女巫救治，仍然死亡。
- 白天：按顺序发言。狼人可以在白天发言阶段自爆，自爆后立即结束白天进入夜晚，当天不放逐。放逐投票最高票者出局；警长拥有1.5票。平票时进入PK：平票者轮流发言后重新投票，再次平票则当天无人出局。
- 猎人：被狼人击杀或被放逐时可以开枪带走一名玩家；被女巫毒杀不能开枪。
- 警长{sheriff}：第一夜后竞选；警长被淘汰后可移交警徽给任意存活玩家或撕毁警徽。"""


def build_prompts(engine, seat: int, request: dict, persona: AIPersona | None) -> tuple[str, str]:
    st = engine.state
    p = st.player(seat)
    role = p.role if p else "villager"
    role_label = ROLE_LABELS.get(role, "未知")

    persona_lines = []
    if persona:
        if persona.name:
            persona_lines.append(f"你的角色名字叫「{persona.name}」。")
        if persona.speaking_style:
            persona_lines.append(f"发言风格：{persona.speaking_style}")
        if persona.reasoning_style:
            persona_lines.append(f"推理风格：{persona.reasoning_style}")
        if persona.risk_preference:
            persona_lines.append(f"风险偏好：{persona.risk_preference}")
        persona_lines.append(f"攻击性：{persona.aggression}/5")
    if not persona_lines:
        persona_lines.append("你是一名普通的狼人杀玩家。")

    system = f"""你正在玩一局中文狼人杀，坐在 {seat} 号位，身份是「{role_label}」。
{_rules_text(st.board_size)}
你的个人设定：
{chr(10).join(' - ' + l for l in persona_lines)}
要求：
1. 严格按照规则行动，只使用合法动作和合法目标。
2. 你只能根据本座位可见的信息推理，绝不要编造你不知道的信息。
3. 发言使用中文，自然、符合你的风格，像真实的桌游玩家。
4. 狼人阵营要隐藏身份、诱导好人；好人阵营要分析发言找狼。
5. 你的输出必须是且仅是一个 JSON 对象，不要输出任何其他文字或解释。"""

    user_lines = [
        f"当前：第 {st.night} 夜 / 第 {st.day} 天，阶段「{PHASE_LABELS.get(st.phase, st.phase)}」",
        f"窗口：{WINDOW_LABELS.get(request.get('window_kind') or '', '')}",
    ]
    user_lines.append("【你掌握的信息】")
    pv = request.get("private_view") or {}
    user_lines.append(f"- 你的身份：{role_label}")
    if role == "wolf" and pv.get("wolves"):
        user_lines.append(f"- 狼人队友：{'、'.join(str(w) + '号' for w in pv['wolves'])}")
    if role == "seer" and pv.get("checks"):
        for c in pv["checks"]:
            label = "狼人" if c["result"] == "wolf" else "好人"
            user_lines.append(f"- 第{c['night']}夜你查验 {c['target']}号：{label}")
    if role == "witch":
        user_lines.append(f"- 解药已用：{'是' if pv.get('save_used') else '否'}；毒药已用：{'是' if pv.get('poison_used') else '否'}")
        if pv.get("victim") is not None:
            user_lines.append(f"- 今夜被狼人袭击的是 {pv['victim']}号")
    if role == "guard":
        user_lines.append(f"- 你上一晚守护的是 {pv.get('last_target')}号" if pv.get("last_target") else "- 你还没有守护过任何人")
    if role == "wolf" and pv.get("wolf_chat"):
        for c in pv["wolf_chat"]:
            user_lines.append(f"- 狼人私聊：{c['seat']}号：{c['text']}")

    user_lines.append("【公开状态】")
    alive = [f"{s}号" for s in st.alive_seats()]
    user_lines.append(f"- 存活：{'、'.join(alive)}")
    dead = [f"{s}号" for s in st.players if not s.alive]
    if dead:
        user_lines.append(f"- 已出局：{'、'.join(dead)}")
    user_lines.append(f"- 警长：{st.sheriff_seat}号" if st.sheriff_seat else "- 当前无警长")
    if st.phase == "day_speech" and st.speech_order:
        user_lines.append(f"- 发言顺序：{'、'.join(str(s) + '号' for s in st.speech_order)}")

    user_lines.append("【事件记录】")
    history = format_history(engine, seat)
    user_lines.append(history if history else "（暂无）")

    user_lines.append("【当前行动】")
    acts = request.get("legal_actions") or []
    if acts:
        user_lines.append(f"- 合法动作：{('、'.join(a['label'] for a in acts))}")
    tgts = request.get("legal_targets") or []
    if tgts:
        user_lines.append(f"- 合法目标：{'、'.join(t['label'] for t in tgts)}")
    else:
        user_lines.append("- 合法目标：无（选择跳过/弃权）")
    user_lines.append(f"- 剩余时间：{request.get('deadline_seconds', 45)} 秒")

    kind = request.get("window_kind") or ""
    schema = _json_schema_text(kind, role, request.get("night_step"))
    user_lines.append("【输出格式】")
    user_lines.append(schema)
    user_lines.append("只输出 JSON 对象本身，不要输出 markdown 代码块或任何解释。")

    return system, "\n".join(user_lines)


def _json_schema_text(kind: str, role: str, night_step: str | None = None) -> str:
    if kind in SPEECH_WINDOWS:
        return ('{"action_type": "speak", "speech": "你的发言内容"}；如果不想发言：{"action_type": "pass"}'
                + ('；狼人可考虑是否自爆：{"action_type": "explode"}' if role == "wolf" else ""))
    if kind in VOTE_WINDOWS:
        return '{"action_type": "vote", "target_seat_number": 目标座位号}；弃权：{"action_type": "vote", "target_seat_number": 0}'
    if kind == "election_apply":
        return '{"action_type": "apply"}（上警）；{"action_type": "withdraw"}（退水）；{"action_type": "pass"}（不上警）'
    if kind == "wolf_kill":
        return ('击杀：{"action_type": "wolf_kill", "target_seat_number": 目标座位号}；空刀：{"action_type": "pass"}；'
                '可选同时发送私聊：{"action_type": "wolf_kill", "target_seat_number": N, "chat_message": "对队友说的话"}')
    if kind == "night_skill":
        if night_step == "guard":
            return '守护：{"action_type": "protect", "target_seat_number": 目标座位号}；不守护：{"action_type": "pass"}'
        if night_step == "seer":
            return '查验：{"action_type": "check", "target_seat_number": 目标座位号}；不查验：{"action_type": "pass"}'
        if night_step == "witch":
            return ('救人：{"action_type": "save", "target_seat_number": 被袭击者}；毒人：{"action_type": "poison", "target_seat_number": 目标}；'
                    '不用药：{"action_type": "pass"}')
        return '{"action_type": "pass"}'
    if kind == "hunter_shot":
        return '开枪：{"action_type": "shoot", "target_seat_number": 目标座位号}；不开枪：{"action_type": "pass"}'
    if kind == "sheriff_transfer":
        return '移交：{"action_type": "transfer", "target_seat_number": 目标座位号}；撕毁：{"action_type": "destroy"}'
    return '{"action_type": "pass"}'
