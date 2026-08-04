"""对局内存状态。纯数据类，支持序列化用于快照恢复。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlayerState:
    seat_number: int
    controller_type: str = "ai"  # human | ai | trustee
    user_id: int | None = None
    user_name: str | None = None
    model_config_id: int | None = None
    persona_id: int | None = None
    persona_name: str | None = None
    ready: bool = False
    alive: bool = True
    role: str | None = None
    consecutive_timeouts: int = 0
    is_host: bool = False

    def to_dict(self) -> dict:
        return {
            "seat_number": self.seat_number,
            "controller_type": self.controller_type,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "model_config_id": self.model_config_id,
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "ready": self.ready,
            "alive": self.alive,
            "role": self.role,
            "consecutive_timeouts": self.consecutive_timeouts,
            "is_host": self.is_host,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlayerState":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k != "seat_number"}, seat_number=d["seat_number"])


@dataclass
class GameState:
    game_id: int
    board_size: int
    status: str = "lobby"  # lobby | running | paused | ended
    phase: str = "lobby"
    night: int = 0
    day: int = 0
    players: list[PlayerState] = field(default_factory=list)
    winner: str | None = None
    end_reason: str | None = None
    speed: int = 1  # 1 | 2 | 3(fast)

    # —— 当前行动窗口（运行时字段，不持久化 deadline/turn_token）——
    window_kind: str | None = None
    acting_seats: list[int] = field(default_factory=list)
    deadline: float = 0.0
    window_duration: float = 0.0
    turn_token: int = 0
    ai_delay_until: float = 0.0

    # —— 夜晚 ——
    night_step: str | None = None  # wolf_kill | guard | seer | witch | resolve
    wolf_votes: dict[int, int] = field(default_factory=dict)  # seat -> target (0=空刀)
    wolf_kill_target: int | None = None
    wolf_chat: list[dict] = field(default_factory=list)  # {seat, text}
    guard_target: int | None = None
    guard_prev_target: int | None = None
    guard_acted: bool = False
    seer_check_target: int | None = None
    seer_acted: bool = False
    seer_checks: list[dict] = field(default_factory=list)  # {night, target, result}
    witch_save_target: int | None = None
    witch_poison_target: int | None = None
    witch_save_used: bool = False
    witch_poison_used: bool = False
    witch_acted: bool = False
    witch_victim: int | None = None  # 本轮被刀目标（告诉女巫）
    night_deaths: list[dict] = field(default_factory=list)  # {seat, mode}

    # —— 警长竞选 ——
    election_stage: str | None = None  # apply | speak | vote | pk_speak | pk_vote
    candidates: list[int] = field(default_factory=list)  # 申请顺序
    election_applies: dict[int, bool] = field(default_factory=dict)
    election_speeches: dict[int, str | None] = field(default_factory=dict)
    election_votes: dict[int, int] = field(default_factory=dict)
    election_pk: list[int] = field(default_factory=list)
    election_pk_speeches: dict[int, str | None] = field(default_factory=dict)
    election_pk_votes: dict[int, int] = field(default_factory=dict)
    sheriff_seat: int | None = None

    # —— 白天 ——
    speech_order: list[int] = field(default_factory=list)
    speech_index: int = 0
    speeches: dict[int, dict] = field(default_factory=dict)  # seat -> {text, skipped}
    lynch_votes: dict[int, int] = field(default_factory=dict)
    lynch_pk: list[int] = field(default_factory=list)
    lynch_pk_speeches: dict[int, dict] = field(default_factory=dict)
    lynch_pk_votes: dict[int, int] = field(default_factory=dict)
    lynch_result_seat: int | None = None

    # —— 结算窗口 ——
    pending_hunter: int | None = None  # 等待开枪的猎人
    hunter_shot_acted: bool = False
    pending_transfer: int | None = None  # 等待移交的已死警长
    transfer_acted: bool = False
    after_transfer: str = "night"  # 移交结束后进入 night | day_speech
    pending_last_words: int | None = None
    last_words_acted: bool = False

    # —— 运行时 ——
    last_seq: int = 0
    next_seq: int = 1
    election_done: bool = False  # 本局是否已产生/放弃警长（9/12 人局在第一夜后）
    roles_revealed: bool = False
    exploded_seat: int | None = None  # 自爆标记，_tick 据此结束白天进入夜晚

    # —— 持久化相关 ——
    def to_dict(self) -> dict:
        """序列化（不含运行时 deadline/turn_token/ai_delay_until）。"""
        d = {
            "game_id": self.game_id,
            "board_size": self.board_size,
            "status": self.status,
            "phase": self.phase,
            "night": self.night,
            "day": self.day,
            "players": [p.to_dict() for p in self.players],
            "winner": self.winner,
            "end_reason": self.end_reason,
            "speed": self.speed,
            "window_kind": self.window_kind,
            "acting_seats": list(self.acting_seats),
            "window_duration": self.window_duration,
            "turn_token": self.turn_token,
            "night_step": self.night_step,
            "wolf_votes": dict(self.wolf_votes),
            "wolf_kill_target": self.wolf_kill_target,
            "wolf_chat": [dict(x) for x in self.wolf_chat],
            "guard_target": self.guard_target,
            "guard_prev_target": self.guard_prev_target,
            "guard_acted": self.guard_acted,
            "seer_check_target": self.seer_check_target,
            "seer_acted": self.seer_acted,
            "seer_checks": [dict(x) for x in self.seer_checks],
            "witch_save_target": self.witch_save_target,
            "witch_poison_target": self.witch_poison_target,
            "witch_save_used": self.witch_save_used,
            "witch_poison_used": self.witch_poison_used,
            "witch_acted": self.witch_acted,
            "witch_victim": self.witch_victim,
            "night_deaths": [dict(x) for x in self.night_deaths],
            "election_stage": self.election_stage,
            "candidates": list(self.candidates),
            "election_applies": dict(self.election_applies),
            "election_speeches": {str(k): v for k, v in self.election_speeches.items()},
            "election_votes": {str(k): v for k, v in self.election_votes.items()},
            "election_pk": list(self.election_pk),
            "election_pk_speeches": {str(k): v for k, v in self.election_pk_speeches.items()},
            "election_pk_votes": {str(k): v for k, v in self.election_pk_votes.items()},
            "sheriff_seat": self.sheriff_seat,
            "speech_order": list(self.speech_order),
            "speech_index": self.speech_index,
            "speeches": {str(k): dict(v) for k, v in self.speeches.items()},
            "lynch_votes": {str(k): v for k, v in self.lynch_votes.items()},
            "lynch_pk": list(self.lynch_pk),
            "lynch_pk_speeches": {str(k): dict(v) for k, v in self.lynch_pk_speeches.items()},
            "lynch_pk_votes": {str(k): v for k, v in self.lynch_pk_votes.items()},
            "lynch_result_seat": self.lynch_result_seat,
            "pending_hunter": self.pending_hunter,
            "hunter_shot_acted": self.hunter_shot_acted,
            "pending_transfer": self.pending_transfer,
            "transfer_acted": self.transfer_acted,
            "after_transfer": self.after_transfer,
            "pending_last_words": self.pending_last_words,
            "last_words_acted": self.last_words_acted,
            "last_seq": self.last_seq,
            "next_seq": self.next_seq,
            "election_done": self.election_done,
            "roles_revealed": self.roles_revealed,
            "exploded_seat": self.exploded_seat,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        st = cls(game_id=d["game_id"], board_size=d["board_size"])
        for k, v in d.items():
            if k == "players":
                st.players = [PlayerState.from_dict(p) for p in v]
            elif k in ("acting_seats", "candidates", "speech_order", "election_pk", "lynch_pk"):
                setattr(st, k, list(v))
            elif k in ("election_applies", "election_votes", "election_pk_votes", "lynch_votes", "lynch_pk_votes", "wolf_votes"):
                setattr(st, k, {int(s): t for s, t in v.items()})
            elif k in ("election_speeches", "election_pk_speeches", "speeches", "lynch_pk_speeches"):
                setattr(st, k, {int(s): dict(t) for s, t in v.items()})
            elif k in ("wolf_chat", "seer_checks", "night_deaths"):
                setattr(st, k, [dict(x) for x in v])
            elif hasattr(st, k):
                setattr(st, k, v)
        return st

    # —— 便捷方法 ——
    def player(self, seat: int) -> PlayerState | None:
        for p in self.players:
            if p.seat_number == seat:
                return p
        return None

    def alive_seats(self) -> list[int]:
        return [p.seat_number for p in self.players if p.alive]

    def alive_roles(self, roles: set[str]) -> list[int]:
        return [p.seat_number for p in self.players if p.alive and p.role in roles]

    def alive_wolves(self) -> list[int]:
        return self.alive_roles({"wolf"})

    def seat_label(self, seat: int | None) -> str:
        if seat is None:
            return "—"
        return f"{seat}号"

    def display_name(self, seat: int) -> str:
        p = self.player(seat)
        if not p:
            return f"{seat}号"
        if p.controller_type == "human":
            return p.user_name or f"{seat}号"
        if p.persona_name:
            return f"AI·{p.persona_name}"
        return f"AI-{seat}号"

    def all_ai(self) -> bool:
        return all(p.controller_type in ("ai", "trustee") for p in self.players)
