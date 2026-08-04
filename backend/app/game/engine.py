"""狼人杀游戏引擎：命令-事件机制、阶段状态机、规则判定、信息隔离、持久化。"""
import asyncio
import logging
import random
import time
from typing import Any

from sqlalchemy import delete, select

from ..config import settings
from ..database import SessionLocal
from ..models import (
    AIPersona,
    ClientCommand,
    Game,
    GameEvent,
    GamePlayer,
    GameResult,
    GameSnapshot,
    ModelConfig,
)
from .constants import (
    BOARDS,
    PHASE_LABELS,
    SHERIFF_BOARDS,
    SPECIAL_ROLES,
    WINDOW_LABELS,
)
from .state import GameState, PlayerState

logger = logging.getLogger("game.engine")

# 允许自爆的阶段
EXPLODE_PHASES = {"day_speech", "sheriff_election", "lynch_pk_speech"}

# 发言类窗口：window_kind -> 事件类型
SPEECH_WINDOWS = {
    "speech": "speech",
    "election_speak": "election_speech",
    "election_pk_speak": "election_pk_speech",
    "lynch_pk_speak": "lynch_pk_speech",
    "last_words": "last_words",
}

# 投票类窗口：window_kind -> (事件类型, 记录字典)
VOTE_WINDOWS = {
    "lynch_vote": ("vote", "lynch_votes"),
    "lynch_pk_vote": ("pk_vote", "lynch_pk_votes"),
    "election_vote": ("election_vote", "election_votes"),
    "election_pk_vote": ("election_pk_vote", "election_pk_votes"),
}


class GameError(Exception):
    """可展示给用户的业务错误。"""

    def __init__(self, message: str, code: str = "invalid_action"):
        super().__init__(message)
        self.message = message
        self.code = code


class GameEngine:
    def __init__(self, state: GameState | None = None, hub: Any = None):
        self.lock = asyncio.Lock()
        self.state = state
        self.hub = hub
        self.events: list[dict] = []
        self._ai_inflight: set[int] = set()
        self._loop_task: asyncio.Task | None = None
        self._closed = False
        self._players_dirty = False
        self._snapshot_required = False
        self._ai: Any = None  # AIOrchestrator，由 main 注入
        self.rng = random.Random()

    # ============================================================ 生命周期
    async def start_loop(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._loop())

    async def stop_loop(self) -> None:
        self._closed = True
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):
                pass
            self._loop_task = None

    async def _loop(self) -> None:
        while not self._closed:
            try:
                await asyncio.sleep(0.4)
                async with self.lock:
                    st = self.state
                    if st is None or st.status != "running":
                        continue
                    if st.ai_delay_until and time.monotonic() < st.ai_delay_until:
                        continue
                    now = time.monotonic()
                    if st.window_kind and st.deadline and now >= st.deadline:
                        await self._force_timeout()
                    await self._tick()
                    self._launch_ai()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("game loop error")

    # ============================================================ 事件
    def _make_event(self, etype: str, actor: int | None, payload: dict,
                    visible_to: list[int] | None = None) -> dict:
        st = self.state
        return {
            "seq": 0,
            "type": etype,
            "actor_seat": actor,
            "day": st.day,
            "night": st.night,
            "phase": st.phase,
            "payload": payload,
            "visible_to": visible_to,
            "ts": 0.0,
        }

    async def _emit(self, events: list[dict], client_cmd: dict | None = None) -> None:
        """分配序号 → 应用到状态 → 持久化 → 广播。必须持有 self.lock。

        注意：phase_change 事件携带生成批次前的状态快照，应用后会重建状态，
        因此必须重放同批次中位于它之前的事件（如死亡、选举结果），
        避免这些事件的状态效果被快照抹掉。
        """
        st = self.state
        batch: list[dict] = []
        for ev in events:
            ev["seq"] = st.next_seq
            ev["ts"] = time.time()
            st.next_seq += 1
            st.last_seq = ev["seq"]
            self.events.append(ev)
            batch.append(ev)
            self._apply_event(st, ev)
            if ev["type"] == "phase_change":
                st = self.state
                for prev in batch[:-1]:
                    self._apply_event(st, prev)
        await self._persist(events, client_cmd)
        if self.hub:
            for ev in events:
                await self.hub.broadcast_event(ev)
            await self.hub.broadcast_view()

    def _apply_event(self, st: GameState, ev: dict) -> None:
        """把事件应用到状态。phase_change 携带完整状态，直接重建。"""
        etype, payload = ev["type"], ev["payload"]
        if etype == "phase_change":
            # phase_change 载荷中的序号是生成批次前的旧值，必须保留运行中的序号
            old_next, old_last = st.next_seq, st.last_seq
            self.state = GameState.from_dict(payload)
            self.state.next_seq = max(self.state.next_seq, old_next)
            self.state.last_seq = max(self.state.last_seq, old_last)
            return
        p = st.player(ev["actor_seat"]) if ev["actor_seat"] else None

        if etype == "game_started":
            st.night = 1
            st.day = 0
            st.status = "running"
        elif etype == "role_assign":
            if p:
                p.role = payload["role"]
        elif etype == "speech":
            st.speeches[ev["actor_seat"]] = {"text": payload.get("text"), "skipped": payload.get("skipped", False)}
        elif etype == "election_speech":
            st.election_speeches[ev["actor_seat"]] = {"text": payload.get("text"), "skipped": payload.get("skipped", False)}
        elif etype == "election_pk_speech":
            st.election_pk_speeches[ev["actor_seat"]] = {"text": payload.get("text"), "skipped": payload.get("skipped", False)}
        elif etype == "lynch_pk_speech":
            st.lynch_pk_speeches[ev["actor_seat"]] = {"text": payload.get("text"), "skipped": payload.get("skipped", False)}
        elif etype == "last_words":
            st.last_words_acted = True
            st.speeches[ev["actor_seat"]] = {"text": payload.get("text"), "skipped": payload.get("skipped", False)}
        elif etype in ("vote", "pk_vote", "election_vote", "election_pk_vote"):
            key = {"vote": "lynch_votes", "pk_vote": "lynch_pk_votes",
                   "election_vote": "election_votes", "election_pk_vote": "election_pk_votes"}[etype]
            getattr(st, key)[ev["actor_seat"]] = payload["target"]
        elif etype == "wolf_vote":
            st.wolf_votes[ev["actor_seat"]] = payload["target"]
        elif etype == "wolf_chat":
            st.wolf_chat.append({"seat": ev["actor_seat"], "text": payload.get("text", "")})
        elif etype == "wolf_kill_result":
            st.wolf_kill_target = payload.get("target")
        elif etype == "guard_action":
            st.guard_target = payload.get("target")
            st.guard_acted = True
        elif etype == "seer_result":
            st.seer_check_target = payload.get("target")
            st.seer_acted = True
            if payload.get("target"):
                st.seer_checks.append({"night": st.night, "target": payload["target"], "result": payload["result"]})
        elif etype == "witch_info":
            st.witch_victim = payload.get("victim")
        elif etype == "witch_action":
            action = payload.get("action")
            if action == "save":
                st.witch_save_target = payload.get("target")
                st.witch_save_used = True
            elif action == "poison":
                st.witch_poison_target = payload.get("target")
                st.witch_poison_used = True
            st.witch_acted = True
        elif etype == "night_deaths":
            st.night_deaths = [dict(d) for d in payload["deaths"]]
            for d in payload["deaths"]:
                dp = st.player(d["seat"])
                if dp:
                    dp.alive = False
        elif etype == "night_result":
            pass  # 公告事件，死亡已由 night_deaths 应用
        elif etype == "hunter_shot":
            st.hunter_shot_acted = True
            if payload.get("target"):
                tp = st.player(payload["target"])
                if tp:
                    tp.alive = False
        elif etype == "lynch_result":
            st.lynch_result_seat = payload.get("seat")
            if payload.get("seat"):
                lp = st.player(payload["seat"])
                if lp:
                    lp.alive = False
        elif etype == "wolf_explode":
            if p:
                p.alive = False
        elif etype == "sheriff_apply":
            st.election_applies[ev["actor_seat"]] = True
            if ev["actor_seat"] not in st.candidates:
                st.candidates.append(ev["actor_seat"])
        elif etype == "sheriff_withdraw":
            st.election_applies[ev["actor_seat"]] = False
            if ev["actor_seat"] in st.candidates:
                st.candidates.remove(ev["actor_seat"])
        elif etype == "sheriff_pass":
            st.election_applies[ev["actor_seat"]] = False
        elif etype == "sheriff_elected":
            st.sheriff_seat = payload["seat"]
            st.election_done = True
        elif etype == "sheriff_transfer":
            st.sheriff_seat = payload.get("target")
            st.transfer_acted = True
        elif etype == "sheriff_destroy":
            st.sheriff_seat = None
            st.transfer_acted = True
        elif etype == "seat_control":
            if p:
                p.controller_type = payload["controller_type"]
                if payload["controller_type"] == "human":
                    p.consecutive_timeouts = 0
        elif etype == "game_over":
            st.status = "ended"
            st.winner = payload.get("winner")
            st.end_reason = payload.get("reason")
            st.roles_revealed = True

    # ============================================================ 持久化
    async def _persist(self, events: list[dict], client_cmd: dict | None) -> None:
        st = self.state
        async with SessionLocal() as db:
            for ev in events:
                db.add(GameEvent(
                    game_id=st.game_id,
                    sequence_number=ev["seq"],
                    type=ev["type"],
                    actor_seat=ev["actor_seat"],
                    day=ev["day"],
                    night=ev["night"],
                    phase=ev["phase"],
                    payload=ev["payload"],
                    visible_to=ev["visible_to"],
                ))
            if self._players_dirty:
                await db.execute(delete(GamePlayer).where(GamePlayer.game_id == st.game_id))
                for p in st.players:
                    if p.controller_type == "empty":
                        continue
                    db.add(GamePlayer(
                        game_id=st.game_id,
                        seat_number=p.seat_number,
                        controller_type=p.controller_type,
                        user_id=p.user_id,
                        model_config_id=p.model_config_id,
                        persona_id=p.persona_id,
                        role=p.role,
                        alive=p.alive,
                        ready=p.ready,
                        is_host=p.is_host,
                        snapshot={"user_name": p.user_name, "persona_name": p.persona_name},
                    ))
                self._players_dirty = False
            if self._snapshot_required:
                db.add(GameSnapshot(
                    game_id=st.game_id,
                    sequence_number=st.last_seq,
                    state=st.to_dict(),
                ))
                self._snapshot_required = False
            row = await db.get(Game, st.game_id)
            if row:
                row.status = st.status
                row.phase = st.phase
                row.winner = st.winner
                row.end_reason = st.end_reason
                if st.status == "ended" and row.ended_at is None:
                    from datetime import datetime
                    row.ended_at = datetime.utcnow()
            if st.status == "ended":
                exists = await db.get(GameResult, st.game_id)
                if not exists:
                    db.add(GameResult(game_id=st.game_id, winner=st.winner or "",
                                      summary={"reason": st.end_reason or ""}))
                    await self._update_user_stats(db, st)
            if client_cmd:
                db.add(ClientCommand(**client_cmd))
            await db.commit()

    async def _update_user_stats(self, db, st: GameState) -> None:
        from ..models import User
        for p in st.players:
            if p.controller_type == "human" and p.user_id and p.role:
                u = await db.get(User, p.user_id)
                if u:
                    u.games_played += 1
                    win = (st.winner == "good") if p.role != "wolf" else (st.winner == "wolf")
                    if win:
                        u.wins += 1

    # ============================================================ 窗口机制
    def _open_window(self, kind: str, seats: list[int], duration: float) -> list[dict]:
        st = self.state
        st.window_kind = kind
        st.acting_seats = list(seats)
        st.deadline = time.monotonic() + duration
        st.window_duration = duration
        st.turn_token += 1
        st.ai_delay_until = 0.0
        self._restore_trustees(seats)
        return [self._make_event("phase_change", None, self._state_payload())]

    def _state_payload(self) -> dict:
        return self.state.to_dict()

    def _restore_trustees(self, seats: list[int]) -> None:
        """重连的真人玩家在下一可操作阶段取回控制权。"""
        if not self.hub:
            return
        for seat in seats:
            p = self.state.player(seat)
            if p and p.controller_type == "trustee" and p.user_id and self.hub.is_user_online(p.user_id):
                p.controller_type = "human"
                p.consecutive_timeouts = 0
                self._players_dirty = True

    def _window_complete(self) -> bool:
        st = self.state
        kind = st.window_kind
        if kind is None:
            return True
        if kind == "wolf_kill":
            wolves = set(st.alive_wolves())
            return bool(wolves) and wolves.issubset(st.wolf_votes.keys())
        if kind == "election_apply":
            alive = set(st.alive_seats())
            return alive.issubset(st.election_applies.keys())
        if not st.acting_seats:
            return True
        actor = st.acting_seats[0]
        if kind in SPEECH_WINDOWS:
            if kind == "speech":
                return actor in st.speeches
            if kind == "election_speak":
                return actor in st.election_speeches
            if kind == "election_pk_speak":
                return actor in st.election_pk_speeches
            if kind == "lynch_pk_speak":
                return actor in st.lynch_pk_speeches
            return st.last_words_acted
        if kind in VOTE_WINDOWS:
            key = VOTE_WINDOWS[kind][1]
            return actor in getattr(st, key)
        if kind == "night_skill":
            step = st.night_step
            if step == "guard":
                return st.guard_acted
            if step == "seer":
                return st.seer_acted
            if step == "witch":
                return st.witch_acted
            return False
        if kind == "hunter_shot":
            return st.hunter_shot_acted
        if kind == "sheriff_transfer":
            return st.transfer_acted
        return False

    async def _tick(self) -> None:
        """推进状态机：胜负判定 → 自爆结算 → 打开下一窗口或阶段转移。持有 self.lock。"""
        st = self.state
        if st.status != "running":
            return
        if st.window_kind and not self._window_complete():
            winner = self._check_win()
            if winner:
                await self._emit([self._game_over_event(winner)])
            elif st.exploded_seat:
                await self._emit(self._start_night([]))
            return
        while True:
            if st.status != "running":
                return
            winner = self._check_win()
            if winner:
                await self._emit([self._game_over_event(winner)])
                return
            if st.exploded_seat:
                await self._emit(self._start_night([]))
                continue
            kind, seats, duration = self._next_window()
            if kind:
                await self._emit(self._open_window(kind, seats, duration))
                return
            events = self._transition()
            if not events:
                return
            await self._emit(events)

    def _game_over_event(self, winner: tuple[str, str]) -> dict:
        st = self.state
        return self._make_event("game_over", None, {
            "winner": winner[0], "reason": winner[1],
            "roles": {p.seat_number: p.role for p in st.players if p.role},
        })

    def _next_window(self) -> tuple[str | None, list[int], float]:
        """返回当前应打开的窗口；无行动者时返回 (None, [], 0) 表示需要转移。"""
        st = self.state
        alive = st.alive_seats()
        to = float(settings.human_action_timeout)

        if st.phase == "night":
            step = st.night_step
            if step == "wolf_kill":
                wolves = [s for s in st.alive_wolves() if s not in st.wolf_votes]
                if wolves:
                    return ("wolf_kill", wolves, float(settings.wolf_window_timeout))
                return (None, [], 0)
            if step == "guard":
                if st.guard_acted:
                    return (None, [], 0)  # 本步骤已完成，等待转移
                guard = st.alive_roles({"guard"})
                return (None, [], 0) if not guard else ("night_skill", guard[:1], to)
            if step == "seer":
                if st.seer_acted:
                    return (None, [], 0)
                seer = st.alive_roles({"seer"})
                return (None, [], 0) if not seer else ("night_skill", seer[:1], to)
            if step == "witch":
                if st.witch_acted:
                    return (None, [], 0)
                witch = st.alive_roles({"witch"})
                return (None, [], 0) if not witch else ("night_skill", witch[:1], to)
            return (None, [], 0)  # resolve

        if st.phase == "sheriff_election":
            stage = st.election_stage or "apply"
            if stage == "apply":
                actors = [s for s in alive if s not in st.election_applies]
                if actors:
                    return ("election_apply", actors, float(settings.apply_window_timeout))
                return (None, [], 0)
            if stage == "speak":
                for c in st.candidates:
                    if c not in st.election_speeches:
                        return ("election_speak", [c], to)
                return (None, [], 0)
            if stage == "vote":
                for s in alive:
                    if s not in st.election_votes:
                        return ("election_vote", [s], to)
                return (None, [], 0)
            if stage == "pk_speak":
                for c in st.election_pk:
                    if c not in st.election_pk_speeches:
                        return ("election_pk_speak", [c], to)
                return (None, [], 0)
            if stage == "pk_vote":
                for s in alive:
                    if s not in st.election_pk_votes:
                        return ("election_pk_vote", [s], to)
                return (None, [], 0)

        if st.phase == "night_result":
            return (None, [], 0)

        if st.phase == "day_speech":
            for s in st.speech_order:
                if s not in st.speeches:
                    return ("speech", [s], to)
            return (None, [], 0)

        if st.phase == "lynch_vote":
            for s in alive:
                if s not in st.lynch_votes:
                    return ("lynch_vote", [s], to)
            return (None, [], 0)

        if st.phase == "lynch_pk_vote":
            for s in alive:
                if s not in st.lynch_pk_votes:
                    return ("lynch_pk_vote", [s], to)
            return (None, [], 0)

        if st.phase == "lynch_pk_speech":
            for s in st.lynch_pk:
                if s not in st.lynch_pk_speeches:
                    return ("lynch_pk_speak", [s], to)
            return (None, [], 0)

        if st.phase == "hunter_shot":
            if not st.hunter_shot_acted and st.pending_hunter:
                return ("hunter_shot", [st.pending_hunter], to)
            return (None, [], 0)

        if st.phase == "sheriff_transfer":
            if not st.transfer_acted and st.pending_transfer:
                return ("sheriff_transfer", [st.pending_transfer], to)
            return (None, [], 0)

        if st.phase == "last_words":
            if not st.last_words_acted and st.pending_last_words:
                return ("last_words", [st.pending_last_words], to)
            return (None, [], 0)

        return (None, [], 0)

    # ============================================================ 阶段转移
    def _transition(self) -> list[dict]:
        st = self.state
        events: list[dict] = []
        self._snapshot_required = True

        if st.phase == "night":
            return self._transition_night(events)
        if st.phase == "sheriff_election":
            return self._transition_election(events)
        if st.phase == "night_result":
            if st.pending_hunter:
                st.hunter_shot_acted = False
                st.phase = "hunter_shot"
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            if st.pending_transfer:
                st.transfer_acted = False
                st.phase = "sheriff_transfer"
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            return self._start_day(events)
        if st.phase == "day_speech":
            st.lynch_votes = {}
            st.lynch_pk = []
            st.lynch_pk_speeches = {}
            st.lynch_pk_votes = {}
            st.lynch_result_seat = None
            st.phase = "lynch_vote"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if st.phase == "lynch_vote":
            return self._tally_lynch(events)
        if st.phase == "lynch_pk_vote":
            return self._tally_lynch(events)
        if st.phase == "lynch_pk_speech":
            st.lynch_pk_votes = {}
            st.phase = "lynch_pk_vote"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if st.phase == "hunter_shot":
            if st.pending_transfer:
                st.transfer_acted = False
                st.phase = "sheriff_transfer"
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            return self._after_shot_or_lastwords(events)
        if st.phase == "sheriff_transfer":
            return self._after_shot_or_lastwords(events)
        if st.phase == "last_words":
            lynched = st.pending_last_words
            lynch_player = st.player(lynched) if lynched else None
            if lynch_player and lynch_player.role == "hunter":
                st.pending_hunter = lynched
                st.hunter_shot_acted = False
                st.phase = "hunter_shot"
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            if st.sheriff_seat == lynched:
                st.pending_transfer = lynched
                st.transfer_acted = False
                st.after_transfer = "night"
                st.phase = "sheriff_transfer"
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            return self._start_night(events)
        if st.phase == "ended":
            return events
        logger.warning("unhandled transition in phase %s", st.phase)
        return events

    def _transition_night(self, events: list[dict]) -> list[dict]:
        st = self.state
        step = st.night_step
        if step == "wolf_kill":
            votes = [t for t in st.wolf_votes.values() if t]
            target = None
            if votes:
                counts: dict[int, int] = {}
                for t in votes:
                    counts[t] = counts.get(t, 0) + 1
                max_count = max(counts.values())
                top = [t for t, c in counts.items() if c == max_count]
                if len(top) == 1:
                    target = top[0]  # 并列最高票 → 空刀
            st.wolf_kill_target = target
            events.append(self._make_event("wolf_kill_result", None,
                                           {"target": target, "votes": dict(st.wolf_votes)},
                                           visible_to=st.alive_wolves()))
            # 进入守卫步骤（重置本夜守卫字段）
            st.guard_target = None
            st.guard_acted = False
            st.night_step = "guard"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if step == "guard":
            # 守卫步骤完成 → 进入预言家步骤
            st.seer_check_target = None
            st.seer_acted = False
            st.night_step = "seer"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if step == "seer":
            # 预言家步骤完成 → 进入女巫步骤
            st.witch_save_target = None
            st.witch_poison_target = None
            st.witch_acted = False
            st.witch_victim = st.wolf_kill_target  # 告知女巫被刀目标
            events.append(self._make_event("witch_info", None,
                                           {"victim": st.witch_victim, "save_used": st.witch_save_used},
                                           visible_to=st.alive_roles({"witch"})))
            st.night_step = "witch"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if step == "witch":
            st.night_step = "resolve"
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        return self._resolve_night(events)

    def _resolve_night(self, events: list[dict]) -> list[dict]:
        st = self.state
        deaths: list[dict] = []
        victim = st.wolf_kill_target
        if victim:
            guarded = st.guard_target == victim
            saved = st.witch_save_target == victim
            protected = guarded != saved  # 同守同救（或同不守不救）→ 死亡
            if not protected:
                deaths.append({"seat": victim, "mode": "wolf"})
        if st.witch_poison_target:
            deaths.append({"seat": st.witch_poison_target, "mode": "poison"})

        events.append(self._make_event("night_deaths", None, {"deaths": deaths}))

        # 猎人被狼刀可在公布时开枪；被毒杀不能开枪
        for d in deaths:
            dp = st.player(d["seat"])
            if dp and dp.role == "hunter" and d["mode"] == "wolf":
                st.pending_hunter = d["seat"]
        if st.sheriff_seat and any(d["seat"] == st.sheriff_seat for d in deaths):
            st.pending_transfer = st.sheriff_seat
            st.after_transfer = "day_speech"

        if st.night == 1 and st.board_size in SHERIFF_BOARDS and not st.election_done:
            st.phase = "sheriff_election"
            st.election_stage = "apply"
            st.candidates = []
            st.election_applies = {}
            st.election_speeches = {}
        else:
            self._enter_night_result(events)
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _enter_night_result(self, events: list[dict]) -> None:
        """进入 night_result 阶段并发布夜间死亡公告。"""
        st = self.state
        st.phase = "night_result"
        events.append(self._make_event("night_result", None, {
            "deaths": [dict(d) for d in st.night_deaths],
            "peaceful": not st.night_deaths,
        }))

    def _transition_election(self, events: list[dict]) -> list[dict]:
        st = self.state
        stage = st.election_stage or "apply"
        if stage == "apply":
            applied = [c for c in st.candidates if st.player(c) and st.player(c).alive]
            if len(applied) == 0:
                st.election_done = True
                st.sheriff_seat = None
                self._enter_night_result(events)
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            if len(applied) == 1:
                events.append(self._make_event("sheriff_elected", None, {"seat": applied[0]}))
                self._enter_night_result(events)
                events.append(self._make_event("phase_change", None, self._state_payload()))
                return events
            st.election_stage = "speak"
            st.election_speeches = {}
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if stage == "speak":
            st.election_stage = "vote"
            st.election_votes = {}
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if stage == "vote":
            return self._tally_election_votes(events)
        if stage == "pk_speak":
            st.election_stage = "pk_vote"
            st.election_pk_votes = {}
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        if stage == "pk_vote":
            return self._tally_election_pk_votes(events)
        return events

    def _tally_election_votes(self, events: list[dict]) -> list[dict]:
        st = self.state
        counts: dict[int, int] = {}
        for t in st.election_votes.values():
            if t:
                counts[t] = counts.get(t, 0) + 1
        top = self._max_votes(counts)
        if len(top) == 1:
            events.append(self._make_event("sheriff_elected", None, {"seat": top[0]}))
        elif len(top) == 0:
            st.election_done = True
            st.sheriff_seat = None
            self._enter_night_result(events)
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        else:
            # 平票 → PK
            st.election_pk = top
            st.election_stage = "pk_speak"
            st.election_pk_speeches = {}
            events.append(self._make_event("phase_change", None, self._state_payload()))
            return events
        self._enter_night_result(events)
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _tally_election_pk_votes(self, events: list[dict]) -> list[dict]:
        st = self.state
        counts: dict[int, int] = {}
        for t in st.election_pk_votes.values():
            if t:
                counts[t] = counts.get(t, 0) + 1
        top = self._max_votes(counts)
        if len(top) == 1:
            events.append(self._make_event("sheriff_elected", None, {"seat": top[0]}))
        else:
            st.election_done = True
            st.sheriff_seat = None  # 二次平票 → 不产生警长
        self._enter_night_result(events)
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _tally_lynch(self, events: list[dict]) -> list[dict]:
        st = self.state
        if st.lynch_pk:
            counts: dict[int, float] = {}
            for t in st.lynch_pk_votes.values():
                if t:
                    counts[t] = counts.get(t, 0) + 1
            top = self._max_votes(counts)
            if len(top) == 1:
                return self._lynch_player(top[0], events)
            # 二次平票 → 当天无人出局
            events.append(self._make_event("lynch_result", None, {"seat": None, "tie": True}))
            return self._start_night(events)
        # 第一轮投票（警长 1.5 票）
        counts: dict[int, float] = {}
        for voter, target in st.lynch_votes.items():
            if not target:
                continue
            w = 1.5 if st.sheriff_seat == voter else 1.0
            counts[target] = counts.get(target, 0) + w
        top = self._max_votes(counts)
        if len(top) == 1:
            return self._lynch_player(top[0], events)
        if len(top) == 0:
            events.append(self._make_event("lynch_result", None, {"seat": None, "tie": False}))
            return self._start_night(events)
        # 平票 → PK 发言与重投
        st.lynch_pk = top
        st.phase = "lynch_pk_speech"
        st.lynch_pk_speeches = {}
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    @staticmethod
    def _max_votes(counts: dict) -> list[int]:
        if not counts:
            return []
        m = max(counts.values())
        return sorted([k for k, v in counts.items() if abs(v - m) < 0.001])

    def _lynch_player(self, seat: int, events: list[dict]) -> list[dict]:
        st = self.state
        events.append(self._make_event("lynch_result", None, {"seat": seat, "tie": False}))
        st.pending_last_words = seat
        st.last_words_acted = False
        st.phase = "last_words"
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _start_day(self, events: list[dict]) -> list[dict]:
        st = self.state
        st.day = st.night
        alive = st.alive_seats()
        order = []
        if st.sheriff_seat and st.sheriff_seat in alive:
            order = [st.sheriff_seat]
            n = st.board_size
            for i in range(1, n):
                s = (st.sheriff_seat + i - 1) % n + 1
                if s != st.sheriff_seat and s in alive:
                    order.append(s)
        else:
            order = alive
        st.speech_order = order
        st.speeches = {}
        st.phase = "day_speech"
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _start_night(self, events: list[dict]) -> list[dict]:
        st = self.state
        st.night += 1
        st.night_step = "wolf_kill"
        st.wolf_votes = {}
        st.wolf_kill_target = None
        st.guard_prev_target = st.guard_target
        st.guard_target = None
        st.guard_acted = False
        st.seer_check_target = None
        st.seer_acted = False
        st.witch_save_target = None
        st.witch_poison_target = None
        st.witch_acted = False
        st.witch_victim = None
        st.night_deaths = []
        st.pending_hunter = None
        st.hunter_shot_acted = False
        st.pending_transfer = None
        st.transfer_acted = False
        st.pending_last_words = None
        st.last_words_acted = False
        st.speech_order = []
        st.speeches = {}
        st.lynch_result_seat = None
        st.election_stage = None
        st.candidates = []
        st.election_applies = {}
        st.election_speeches = {}
        st.election_votes = {}
        st.election_pk = []
        st.election_pk_speeches = {}
        st.election_pk_votes = {}
        st.exploded_seat = None
        st.phase = "night"
        events.append(self._make_event("phase_change", None, self._state_payload()))
        return events

    def _after_shot_or_lastwords(self, events: list[dict]) -> list[dict]:
        st = self.state
        if st.after_transfer == "day_speech":
            return self._start_day(events)
        return self._start_night(events)

    def _check_win(self) -> tuple[str, str] | None:
        st = self.state
        wolves = st.alive_wolves()
        if not wolves:
            return ("good", "狼人全部出局")
        alive = st.alive_seats()
        if not alive:
            return ("wolf", "好人全部出局")
        villagers = [s for s in alive if st.player(s).role == "villager"]
        specials = [s for s in alive if st.player(s).role in SPECIAL_ROLES]
        if not villagers:
            return ("wolf", "平民全部出局")
        if not specials:
            return ("wolf", "神职全部出局")
        return None

    # ============================================================ 超时处理
    async def _force_timeout(self) -> None:
        st = self.state
        if not st.acting_seats:
            st.deadline = 0
            return
        ai_pending = [s for s in st.acting_seats
                      if st.player(s) and st.player(s).controller_type in ("ai", "trustee")]
        if ai_pending and all(s in self._ai_inflight for s in ai_pending):
            st.deadline = time.monotonic() + 10  # AI 调用在途，延长等待
            return
        events: list[dict] = []
        for seat in st.acting_seats:
            p = st.player(seat)
            if not p:
                continue
            # 遗言/警徽移交/猎人开枪 窗口的行动者可能已出局，超时同样需要跳过
            dead_ok = st.window_kind in ("last_words", "sheriff_transfer", "hunter_shot")
            if not p.alive and not dead_ok:
                continue
            if p.controller_type in ("ai", "trustee"):
                if seat in self._ai_inflight:
                    continue
                # AI 无在途调用（未配置模型等）→ 直接执行兜底跳过
                _etype, _payload = self._skip_event_for(seat)
                events.append(self._make_event(_etype, seat, _payload))
                continue
            p.consecutive_timeouts += 1
            if p.consecutive_timeouts >= 2:
                p.controller_type = "trustee"
                self._players_dirty = True
                events.append(self._make_event("seat_control", seat, {"controller_type": "trustee"}))
            _etype, _payload = self._skip_event_for(seat)
            events.append(self._make_event(_etype, seat, _payload))
        if events:
            await self._emit(events)
        await self._tick()

    def _skip_event_for(self, seat: int) -> tuple[str, dict]:
        """超时/弃权对应的事件。"""
        kind = self.state.window_kind or ""
        if kind == "wolf_kill":
            return "wolf_vote", {"target": 0}
        if kind == "election_apply":
            return "sheriff_pass", {}
        if kind in VOTE_WINDOWS:
            return VOTE_WINDOWS[kind][0], {"target": 0}
        if kind in SPEECH_WINDOWS:
            return SPEECH_WINDOWS[kind], {"skipped": True}
        if kind == "night_skill":
            step = self.state.night_step
            if step == "guard":
                return "guard_action", {"target": None, "skipped": True}
            if step == "seer":
                return "seer_result", {"target": None, "skipped": True}
            if step == "witch":
                return "witch_action", {"action": None, "skipped": True}
        if kind == "hunter_shot":
            return "hunter_shot", {"target": None, "skipped": True}
        if kind == "sheriff_transfer":
            return "sheriff_destroy", {}
        return "speech", {"skipped": True}

    # ============================================================ AI 启动
    def _launch_ai(self) -> None:
        st = self.state
        if self._ai is None or not st.acting_seats:
            return
        for seat in st.acting_seats:
            p = st.player(seat)
            if not p or p.controller_type not in ("ai", "trustee"):
                continue
            if seat in self._ai_inflight:
                continue
            self._ai_inflight.add(seat)
            asyncio.create_task(self._ai.run_ai_turn(self, seat, st.turn_token))

    # ============================================================ 命令处理
    async def process_ws_command(self, user_id: int, request_id: str, cmd_type: str, payload: dict) -> dict:
        """真人通过 WebSocket 提交命令。"""
        async with self.lock:
            st = self.state
            seat = None
            for p in st.players:
                if p.user_id == user_id and p.controller_type == "human":
                    seat = p.seat_number
                    break
            if seat is None:
                return {"ok": False, "error": "你不在本局对局中"}
            try:
                await self._apply_command(cmd_type, payload, seat, request_id)
                return {"ok": True}
            except GameError as e:
                return {"ok": False, "error": e.message, "code": e.code}

    async def commit_ai(self, seat: int, token: int, result: dict | None) -> None:
        """AI 结果提交；result=None 表示兜底动作。"""
        async with self.lock:
            self._ai_inflight.discard(seat)
            st = self.state
            if st.status != "running" or token != st.turn_token or seat not in st.acting_seats:
                return  # 过期结果，丢弃
            cmds = self._ai_result_to_commands(seat, result)
            for idx, (cmd_type, payload) in enumerate(cmds):
                rid = f"ai:{token}:{seat}:{idx}"
                try:
                    await self._apply_command(cmd_type, payload, seat, rid)
                except GameError:
                    if idx == len(cmds) - 1:
                        try:
                            await self._apply_command(*self._fallback_command(seat), seat, rid + ":fb")
                        except GameError:
                            return  # 窗口已变，静默丢弃

    async def _apply_command(self, cmd_type: str, payload: dict, seat: int, request_id: str | None) -> None:
        st = self.state
        if st.status != "running":
            raise GameError("对局未在进行中")
        p = st.player(seat)
        if p is None:
            raise GameError("座位不存在")
        if request_id:
            async with SessionLocal() as db:
                exists = await db.scalar(
                    select(ClientCommand).where(
                        ClientCommand.game_id == st.game_id,
                        ClientCommand.request_id == request_id))
                if exists:
                    return  # 幂等：重复请求直接忽略

        events = self._handle_command(cmd_type, payload, seat)
        client_cmd = None
        if request_id:
            client_cmd = {
                "game_id": st.game_id,
                "request_id": request_id,
                "seat_number": seat,
                "type": cmd_type,
                "payload": payload,
                "result_seq": st.next_seq + len(events) - 1,
            }
        await self._emit(events, client_cmd)
        await self._tick()

    def _handle_command(self, cmd_type: str, payload: dict, seat: int) -> list[dict]:
        st = self.state
        p = st.player(seat)
        assert p is not None

        if cmd_type == "wolf_chat":
            if p.role != "wolf" or not p.alive:
                raise GameError("只有存活的狼人可以私聊")
            if st.window_kind != "wolf_kill":
                raise GameError("现在不是狼人夜聊时间")
            text = str(payload.get("text", "")).strip()
            if not text:
                raise GameError("消息不能为空")
            return [self._make_event("wolf_chat", seat, {"text": text[:500]}, visible_to=st.alive_wolves())]

        if cmd_type == "wolf_explode":
            if p.role != "wolf" or not p.alive:
                raise GameError("只有存活的狼人可以自爆")
            if st.phase not in EXPLODE_PHASES:
                raise GameError("当前阶段不能自爆")
            if st.phase == "sheriff_election" and st.election_stage not in ("speak", "pk_speak"):
                raise GameError("当前阶段不能自爆")
            st.exploded_seat = seat
            return [self._make_event("wolf_explode", seat, {})]

        # —— 以下命令必须是当前窗口行动者 ——
        if seat not in st.acting_seats:
            raise GameError("现在不需要你行动")
        if not p.alive and st.window_kind not in ("sheriff_transfer", "last_words", "hunter_shot"):
            raise GameError("你已经出局")

        kind = st.window_kind

        if cmd_type == "pass":
            _etype, _payload = self._skip_event_for(seat)
            return [self._make_event(_etype, seat, _payload)]

        if kind in SPEECH_WINDOWS:
            if cmd_type != "speak":
                raise GameError("当前需要发言")
            text = str(payload.get("text", "")).strip()
            if not text:
                raise GameError("发言不能为空")
            if len(text) > 1000:
                raise GameError("发言过长")
            return [self._make_event(SPEECH_WINDOWS[kind], seat, {"text": text, "skipped": False})]

        if kind in VOTE_WINDOWS:
            if cmd_type != "vote":
                raise GameError("当前需要投票")
            target = int(payload.get("target") or 0)
            if target == 0:
                return [self._make_event(VOTE_WINDOWS[kind][0], seat, {"target": 0})]
            tp = st.player(target)
            if not tp or not tp.alive:
                raise GameError("目标无效")
            if target == seat:
                raise GameError("不能投自己")
            if kind in ("election_vote", "election_pk_vote"):
                pool = st.candidates if kind == "election_vote" else st.election_pk
                if target not in pool:
                    raise GameError("只能投票给警长候选人")
            elif kind == "lynch_pk_vote" and target not in st.lynch_pk:
                raise GameError("只能投票给PK候选人")
            return [self._make_event(VOTE_WINDOWS[kind][0], seat, {"target": target})]

        if kind == "election_apply":
            if cmd_type != "sheriff_action":
                raise GameError("当前需要选择是否上警")
            action = payload.get("action")
            if action == "apply":
                return [self._make_event("sheriff_apply", seat, {})]
            if action == "withdraw":
                if seat not in st.candidates:
                    raise GameError("你还没有上警")
                return [self._make_event("sheriff_withdraw", seat, {})]
            if action == "pass":
                return [self._make_event("sheriff_pass", seat, {})]
            raise GameError("无效的上警操作")

        if kind == "wolf_kill":
            if cmd_type != "use_skill":
                raise GameError("狼人需要在夜间选择击杀目标")
            skill = payload.get("skill")
            if skill != "wolf_kill":
                raise GameError("狼人夜间只能选择击杀")
            target = int(payload.get("target") or 0)
            if target == 0:
                return [self._make_event("wolf_vote", seat, {"target": 0}, visible_to=st.alive_wolves())]
            tp = st.player(target)
            if not tp or not tp.alive:
                raise GameError("目标无效")
            if tp.role == "wolf" or target == seat:
                raise GameError("不能击杀狼人队友或自己")
            return [self._make_event("wolf_vote", seat, {"target": target}, visible_to=st.alive_wolves())]

        if kind == "night_skill":
            if cmd_type != "use_skill":
                raise GameError("当前需要选择夜间技能")
            skill = payload.get("skill")
            raw_target = payload.get("target")
            target = int(raw_target) if raw_target else None
            step = st.night_step
            if step == "guard":
                if skill != "guard_protect":
                    raise GameError("守卫需要选择守护目标")
                if target is None:
                    return [self._make_event("guard_action", seat, {"target": None, "skipped": True}, visible_to=[seat])]
                tp = st.player(target)
                if not tp or not tp.alive:
                    raise GameError("目标无效")
                if target == st.guard_prev_target:
                    raise GameError("守卫不能连续两晚守护同一目标")
                return [self._make_event("guard_action", seat, {"target": target}, visible_to=[seat])]
            if step == "seer":
                if skill != "seer_check":
                    raise GameError("预言家需要选择查验目标")
                if target is None:
                    return [self._make_event("seer_result", seat, {"target": None, "skipped": True})]
                tp = st.player(target)
                if not tp or not tp.alive:
                    raise GameError("目标无效")
                if target == seat:
                    raise GameError("不能查验自己")
                result = "wolf" if tp.role == "wolf" else "good"
                return [self._make_event("seer_result", seat,
                                         {"target": target, "result": result, "skipped": False},
                                         visible_to=[seat])]
            if step == "witch":
                if skill not in ("witch_save", "witch_poison"):
                    raise GameError("女巫需要选择用药")
                if skill == "witch_save":
                    if st.witch_save_used:
                        raise GameError("解药已使用")
                    if target is None:
                        return [self._make_event("witch_action", seat, {"action": None, "skipped": True})]
                    if target != st.witch_victim:
                        raise GameError("只能救被狼人击杀的玩家")
                    if target == seat and st.night != 1:
                        raise GameError("只有首夜可以自救")
                    return [self._make_event("witch_action", seat,
                                             {"action": "save", "target": target}, visible_to=[seat])]
                if st.witch_poison_used:
                    raise GameError("毒药已使用")
                if target is None:
                    return [self._make_event("witch_action", seat, {"action": None, "skipped": True})]
                tp = st.player(target)
                if not tp or not tp.alive:
                    raise GameError("目标无效")
                if target == seat:
                    raise GameError("不能毒自己")
                return [self._make_event("witch_action", seat,
                                         {"action": "poison", "target": target}, visible_to=[seat])]
            raise GameError("无效的技能")

        if kind == "hunter_shot":
            if cmd_type != "use_skill":
                raise GameError("猎人需要选择是否开枪")
            skill = payload.get("skill")
            if skill != "hunter_shot":
                raise GameError("猎人只能选择开枪")
            raw_target = payload.get("target")
            target = int(raw_target) if raw_target else None
            if target is None:
                return [self._make_event("hunter_shot", seat, {"target": None, "skipped": True})]
            tp = st.player(target)
            if not tp or not tp.alive:
                raise GameError("目标无效")
            if target == seat:
                raise GameError("不能枪自己")
            return [self._make_event("hunter_shot", seat, {"target": target})]

        if kind == "sheriff_transfer":
            if cmd_type != "sheriff_action":
                raise GameError("需要选择警徽移交或撕毁")
            action = payload.get("action")
            if action == "destroy":
                return [self._make_event("sheriff_destroy", seat, {})]
            if action == "transfer":
                raw_target = payload.get("target")
                target = int(raw_target) if raw_target else 0
                tp = st.player(target)
                if not tp or not tp.alive:
                    raise GameError("目标无效")
                return [self._make_event("sheriff_transfer", seat, {"target": target})]
            raise GameError("无效的警徽操作")

        raise GameError("无法识别的命令")

    # ============================================================ AI 请求构建
    def build_ai_request(self, seat: int) -> dict:
        st = self.state
        p = st.player(seat)
        return {
            "game_id": st.game_id,
            "seat_number": seat,
            "phase": st.phase,
            "window_kind": st.window_kind,
            "night_step": st.night_step,
            "night": st.night,
            "day": st.day,
            "private_view": self.private_info_for(seat),
            "legal_actions": self.legal_actions_for(seat),
            "legal_targets": self.legal_targets_for(seat),
            "deadline_seconds": max(1, int(st.deadline - time.monotonic())) if st.deadline else 45,
        }

    def _ai_result_to_commands(self, seat: int, result: dict | None) -> list[tuple[str, dict]]:
        """把模型输出转为命令列表（可同时含私聊与击杀）；非法输出走兜底。"""
        st = self.state
        kind = st.window_kind or ""
        if not result or not isinstance(result, dict):
            return [self._fallback_command(seat)]
        action = str(result.get("action_type") or result.get("action") or "pass")
        text = str(result.get("speech") or "").strip()
        chat = str(result.get("chat_message") or "").strip()
        target = result.get("target_seat_number")
        sa = result.get("sheriff_action")
        cmds: list[tuple[str, dict]] = []

        if kind in SPEECH_WINDOWS:
            if action in ("speak", "speech") and text:
                return [("speak", {"text": text})]
            return [("pass", {})]
        if kind in VOTE_WINDOWS:
            if action == "vote" and isinstance(target, int) and target > 0:
                return [("vote", {"target": target})]
            return [("vote", {"target": 0})]
        if kind == "election_apply":
            if action == "apply":
                return [("sheriff_action", {"action": "apply"})]
            if action == "withdraw":
                return [("sheriff_action", {"action": "withdraw"})]
            return [("sheriff_action", {"action": "pass"})]
        if kind == "wolf_kill":
            if chat:
                cmds.append(("wolf_chat", {"text": chat}))
            if action in ("vote", "wolf_kill") and isinstance(target, int) and target > 0:
                cmds.append(("use_skill", {"skill": "wolf_kill", "target": target}))
            else:
                cmds.append(("use_skill", {"skill": "wolf_kill", "target": 0}))
            return cmds
        if kind == "night_skill":
            step = st.night_step
            if step == "guard":
                if action == "protect" and isinstance(target, int) and target > 0:
                    return [("use_skill", {"skill": "guard_protect", "target": target})]
                return [("use_skill", {"skill": "guard_protect", "target": None})]
            if step == "seer":
                if action == "check" and isinstance(target, int) and target > 0:
                    return [("use_skill", {"skill": "seer_check", "target": target})]
                return [("use_skill", {"skill": "seer_check", "target": None})]
            if step == "witch":
                if action == "save" and isinstance(target, int) and target > 0:
                    return [("use_skill", {"skill": "witch_save", "target": target})]
                if action == "poison" and isinstance(target, int) and target > 0:
                    return [("use_skill", {"skill": "witch_poison", "target": target})]
                return [("use_skill", {"skill": "witch_save", "target": None})]
            return [("pass", {})]
        if kind == "hunter_shot":
            if action == "shoot" and isinstance(target, int) and target > 0:
                return [("use_skill", {"skill": "hunter_shot", "target": target})]
            return [("use_skill", {"skill": "hunter_shot", "target": None})]
        if kind == "sheriff_transfer":
            a = sa.get("action") if isinstance(sa, dict) else None
            if action == "transfer" and isinstance(target, int) and target > 0:
                return [("sheriff_action", {"action": "transfer", "target": target})]
            if a == "transfer" and isinstance(sa.get("target"), int):
                return [("sheriff_action", {"action": "transfer", "target": sa["target"]})]
            return [("sheriff_action", {"action": "destroy"})]
        return [("pass", {})]

    def _fallback_command(self, seat: int) -> tuple[str, dict]:
        """模型彻底失败时的确定性兜底：弃权/跳过。"""
        return ("pass", {})

    # ============================================================ 可见信息
    def legal_actions_for(self, seat: int) -> list[dict]:
        st = self.state
        p = st.player(seat)
        if not p:
            return []
        if not p.alive and st.window_kind not in ("sheriff_transfer", "last_words"):
            return []
        if seat not in st.acting_seats:
            return []
        kind = st.window_kind or ""
        out: list[dict] = []
        if kind in SPEECH_WINDOWS:
            out.append({"type": "speak", "label": "发言"})
            if p.role == "wolf":
                out.append({"type": "wolf_explode", "label": "自爆"})
            out.append({"type": "pass", "label": "跳过"})
        elif kind in VOTE_WINDOWS:
            out.append({"type": "vote", "label": "投票"})
            out.append({"type": "pass", "label": "弃权"})
        elif kind == "election_apply":
            out.append({"type": "sheriff_action", "action": "apply", "label": "上警"})
            if seat in st.candidates:
                out.append({"type": "sheriff_action", "action": "withdraw", "label": "退水"})
            out.append({"type": "sheriff_action", "action": "pass", "label": "不上警"})
        elif kind == "wolf_kill":
            out.append({"type": "use_skill", "skill": "wolf_kill", "label": "击杀目标"})
            out.append({"type": "wolf_chat", "label": "狼人私聊"})
            out.append({"type": "pass", "label": "空刀"})
        elif kind == "night_skill":
            step = st.night_step
            if step == "guard":
                out.append({"type": "use_skill", "skill": "guard_protect", "label": "守护目标"})
            elif step == "seer":
                out.append({"type": "use_skill", "skill": "seer_check", "label": "查验目标"})
            elif step == "witch":
                if not st.witch_save_used and st.witch_victim:
                    out.append({"type": "use_skill", "skill": "witch_save", "label": "使用解药"})
                if not st.witch_poison_used:
                    out.append({"type": "use_skill", "skill": "witch_poison", "label": "使用毒药"})
            out.append({"type": "pass", "label": "不使用"})
        elif kind == "hunter_shot":
            out.append({"type": "use_skill", "skill": "hunter_shot", "label": "开枪"})
            out.append({"type": "pass", "label": "不开枪"})
        elif kind == "sheriff_transfer":
            out.append({"type": "sheriff_action", "action": "transfer", "label": "移交警徽"})
            out.append({"type": "sheriff_action", "action": "destroy", "label": "撕毁警徽"})
        return out

    def legal_targets_for(self, seat: int) -> list[dict]:
        st = self.state
        p = st.player(seat)
        if not p:
            return []
        if not p.alive and st.window_kind not in ("sheriff_transfer", "last_words"):
            return []
        kind = st.window_kind or ""
        alive = [s for s in st.alive_seats() if s != seat]
        if kind in ("lynch_vote", "lynch_pk_vote", "election_vote", "election_pk_vote"):
            if kind in ("election_vote", "election_pk_vote"):
                pool = st.candidates if kind == "election_vote" else st.election_pk
                alive = [s for s in pool if s != seat and st.player(s) and st.player(s).alive]
            elif kind == "lynch_pk_vote":
                alive = [s for s in st.lynch_pk if s != seat and st.player(s) and st.player(s).alive]
            return [{"seat": s, "label": f"{s}号·{st.display_name(s)}"} for s in alive]
        if kind == "wolf_kill":
            return [{"seat": s, "label": f"{s}号·{st.display_name(s)}"}
                    for s in alive if st.player(s).role != "wolf"]
        if kind == "night_skill":
            step = st.night_step
            out: list[dict] = []
            if step == "guard":
                out = [{"seat": s, "label": f"{s}号·{st.display_name(s)}"}
                       for s in alive if s != st.guard_prev_target]
            elif step == "seer":
                out = [{"seat": s, "label": f"{s}号·{st.display_name(s)}"} for s in alive]
            elif step == "witch":
                if not st.witch_save_used and st.witch_victim and (st.witch_victim != seat or st.night == 1):
                    out.append({"seat": st.witch_victim, "label": f"💊 救 {st.witch_victim}号·{st.display_name(st.witch_victim)}", "kind": "save"})
                if not st.witch_poison_used:
                    out += [{"seat": s, "label": f"☠️ 毒 {s}号·{st.display_name(s)}", "kind": "poison"} for s in alive]
            return out
        if kind == "hunter_shot":
            return [{"seat": s, "label": f"{s}号·{st.display_name(s)}"} for s in alive]
        if kind == "sheriff_transfer":
            return [{"seat": s, "label": f"{s}号·{st.display_name(s)}"} for s in st.alive_seats()]
        return []

    def private_info_for(self, seat: int) -> dict:
        st = self.state
        p = st.player(seat)
        info: dict = {"role": p.role if p else None}
        if p and p.role == "wolf":
            info["wolves"] = [x.seat_number for x in st.players if x.role == "wolf"]
            info["wolf_chat"] = [dict(c) for c in st.wolf_chat]
            info["wolf_votes"] = dict(st.wolf_votes)
            info["wolf_kill_target"] = st.wolf_kill_target
        if p and p.role == "seer":
            info["checks"] = [dict(c) for c in st.seer_checks]
        if p and p.role == "witch":
            info["save_used"] = st.witch_save_used
            info["poison_used"] = st.witch_poison_used
            info["victim"] = st.witch_victim
            info["save_target"] = st.witch_save_target
            info["poison_target"] = st.witch_poison_target
        if p and p.role == "guard":
            info["last_target"] = st.guard_prev_target
            info["current_target"] = st.guard_target
        if p and p.role == "hunter":
            info["can_shoot"] = st.pending_hunter == seat
        return info

    def build_view(self, viewer_seat: int | None) -> dict:
        st = self.state
        players = []
        for p in st.players:
            if p.controller_type == "empty":
                continue
            players.append({
                "seat": p.seat_number,
                "name": st.display_name(p.seat_number),
                "controller_type": p.controller_type,
                "user_id": p.user_id,
                "alive": p.alive,
                "ready": p.ready,
                "is_host": p.is_host,
                "role": p.role if (st.roles_revealed or (viewer_seat == p.seat_number)) else None,
                "persona_name": p.persona_name,
            })
        me = None
        if viewer_seat is not None:
            p = st.player(viewer_seat)
            if p:
                me = {
                    "seat": p.seat_number,
                    "controller_type": p.controller_type,
                    "role": p.role,
                    "alive": p.alive,
                    "is_host": p.is_host,
                }
        game = {
            "game_id": st.game_id,
            "board_size": st.board_size,
            "status": st.status,
            "phase": st.phase,
            "phase_label": PHASE_LABELS.get(st.phase, st.phase),
            "window_kind": st.window_kind,
            "window_label": WINDOW_LABELS.get(st.window_kind or "", ""),
            "night": st.night,
            "day": st.day,
            "sheriff_seat": st.sheriff_seat,
            "winner": st.winner,
            "end_reason": st.end_reason,
            "speed": st.speed,
            "acting_seats": list(st.acting_seats),
            "deadline": max(0, st.deadline - time.monotonic()) if st.deadline else 0,
            "election_stage": st.election_stage,
            "night_step": st.night_step,
            "is_all_ai": st.all_ai(),
        }
        view = {
            "game": game,
            "players": players,
            "me": me,
            "legal_actions": self.legal_actions_for(viewer_seat) if viewer_seat else [],
            "legal_targets": self.legal_targets_for(viewer_seat) if viewer_seat else [],
            "private": self.private_info_for(viewer_seat) if viewer_seat else {},
        }
        if st.roles_revealed:
            view["roles_revealed"] = {p.seat_number: p.role for p in st.players if p.role}
        return view

    # ============================================================ 大厅（REST）
    async def join(self, user_id: int, user_name: str, seat_number: int | None) -> dict:
        st = self.state
        if st.status != "lobby":
            raise GameError("对局已开始")
        existing = next((p for p in st.players if p.user_id == user_id and p.controller_type == "human"), None)
        if existing:
            return {"seat": existing.seat_number}
        if seat_number is not None:
            p = st.player(seat_number)
            if not p:
                raise GameError("座位不存在")
            if p.controller_type != "empty":
                raise GameError("该座位已被占用")
            target = p
        else:
            target = next((p for p in st.players if p.controller_type == "empty"), None)
            if target is None:
                raise GameError("座位已满")
        target.controller_type = "human"
        target.user_id = user_id
        target.user_name = user_name
        target.ready = False
        target.consecutive_timeouts = 0
        self._players_dirty = True
        self._snapshot_required = True
        await self._persist_lobby()
        return {"seat": target.seat_number}

    async def leave(self, user_id: int) -> None:
        st = self.state
        p = next((x for x in st.players if x.user_id == user_id and x.controller_type == "human"), None)
        if not p:
            return
        if st.status == "lobby":
            p.controller_type = "empty"
            p.user_id = None
            p.user_name = None
            p.ready = False
            p.model_config_id = None
            p.persona_id = None
            p.persona_name = None
        else:
            # 对局中退出 → AI 托管
            p.controller_type = "trustee"
            if self.hub:
                await self.hub.broadcast_event(self._make_event("seat_control", p.seat_number,
                                                                {"controller_type": "trustee"}))
                await self.hub.broadcast_view()
        self._players_dirty = True
        self._snapshot_required = True
        await self._persist_lobby()

    async def set_ready(self, user_id: int, ready: bool) -> None:
        st = self.state
        if st.status != "lobby":
            raise GameError("对局已开始")
        p = next((x for x in st.players if x.user_id == user_id and x.controller_type == "human"), None)
        if not p:
            raise GameError("你不在座位上")
        p.ready = ready
        self._players_dirty = True
        self._snapshot_required = True
        await self._persist_lobby()

    async def ai_seat(self, seat_number: int, action: str, model_config_id: int | None,
                      persona_id: int | None) -> None:
        st = self.state
        if st.status != "lobby":
            raise GameError("对局已开始")
        p = st.player(seat_number)
        if not p:
            raise GameError("座位不存在")
        if action == "add":
            if p.controller_type != "empty":
                raise GameError("该座位已有人")
            await self._apply_ai_defaults(p, model_config_id, persona_id)
            p.controller_type = "ai"
            p.ready = True
        elif action == "remove":
            if p.controller_type not in ("ai", "empty"):
                raise GameError("只能移除AI座位")
            p.controller_type = "empty"
            p.user_id = None
            p.model_config_id = None
            p.persona_id = None
            p.persona_name = None
        else:
            raise GameError("未知操作")
        self._players_dirty = True
        self._snapshot_required = True
        await self._persist_lobby()

    async def ai_fill(self, model_config_id: int | None, persona_id: int | None) -> None:
        st = self.state
        if st.status != "lobby":
            raise GameError("对局已开始")
        for p in st.players:
            if p.controller_type == "empty":
                await self._apply_ai_defaults(p, model_config_id, persona_id)
                p.controller_type = "ai"
                p.ready = True
        self._players_dirty = True
        self._snapshot_required = True
        await self._persist_lobby()

    async def _apply_ai_defaults(self, p: PlayerState, model_config_id: int | None, persona_id: int | None) -> None:
        async with SessionLocal() as db:
            cfg = None
            if model_config_id:
                cfg = await db.get(ModelConfig, model_config_id)
            if cfg is None:
                cfg = (await db.execute(
                    select(ModelConfig).where(ModelConfig.enabled.is_(True))
                    .order_by(ModelConfig.is_default_fallback.desc(), ModelConfig.id))).scalars().first()
            persona = None
            if persona_id:
                persona = await db.get(AIPersona, persona_id)
            if persona is None:
                persona = (await db.execute(select(AIPersona).order_by(AIPersona.id))).scalars().first()
        if cfg is None:
            raise GameError("尚未配置可用模型，请先到后台添加模型配置")
        p.model_config_id = cfg.id
        p.persona_id = persona.id if persona else None
        p.persona_name = persona.name if persona else "通用"

    async def start_game(self) -> None:
        st = self.state
        if st.status != "lobby":
            raise GameError("对局已开始")
        occupied = [p for p in st.players if p.controller_type != "empty"]
        if len(occupied) != st.board_size:
            raise GameError(f"需要 {st.board_size} 名玩家，当前 {len(occupied)} 名")
        not_ready = [p for p in occupied if p.controller_type == "human" and not p.ready]
        if not_ready:
            raise GameError(f"{', '.join(str(p.seat_number) for p in not_ready)} 号座位尚未准备")

        roles = list(BOARDS[st.board_size])
        self.rng.shuffle(roles)
        st.phase = "night"
        st.night = 1
        st.day = 0
        st.status = "running"
        st.winner = None
        st.election_done = False
        st.sheriff_seat = None
        st.night_step = "wolf_kill"
        st.wolf_votes = {}
        st.exploded_seat = None

        events = [self._make_event("game_started", None, {"board_size": st.board_size})]
        for i, p in enumerate(st.players):
            p.role = roles[i]
            events.append(self._make_event("role_assign", p.seat_number, {"role": p.role},
                                           visible_to=[p.seat_number]))
        events.append(self._make_event("phase_change", None, self._state_payload()))
        self._players_dirty = True
        self._snapshot_required = True
        await self._emit(events)
        await self._tick()
        await self.start_loop()

    async def _persist_lobby(self) -> None:
        """大厅状态直接持久化（无事件流）。"""
        st = self.state
        async with SessionLocal() as db:
            if self._players_dirty:
                await db.execute(delete(GamePlayer).where(GamePlayer.game_id == st.game_id))
                for p in st.players:
                    if p.controller_type == "empty":
                        continue
                    db.add(GamePlayer(
                        game_id=st.game_id, seat_number=p.seat_number,
                        controller_type=p.controller_type, user_id=p.user_id,
                        model_config_id=p.model_config_id, persona_id=p.persona_id,
                        role=p.role, alive=p.alive, ready=p.ready, is_host=p.is_host,
                        snapshot={"user_name": p.user_name, "persona_name": p.persona_name}))
                self._players_dirty = False
            if self._snapshot_required:
                db.add(GameSnapshot(game_id=st.game_id, sequence_number=st.last_seq, state=st.to_dict()))
                self._snapshot_required = False
            row = await db.get(Game, st.game_id)
            if row:
                row.status = st.status
                row.phase = st.phase
            await db.commit()

    # ============================================================ 观战控制
    async def set_speed(self, speed: int) -> None:
        async with self.lock:
            if speed not in (1, 2, 3):
                raise GameError("速度只能为 1 / 2 / 3")
            self.state.speed = speed
            async with SessionLocal() as db:
                row = await db.get(Game, self.state.game_id)
                if row:
                    row.status = self.state.status
                await db.commit()

    async def pause(self) -> None:
        async with self.lock:
            if self.state.status != "running":
                raise GameError("对局不在进行中")
            self.state.status = "paused"
            self._snapshot_required = True
            await self._persist_lobby()

    async def resume(self) -> None:
        async with self.lock:
            if self.state.status != "paused":
                raise GameError("对局未暂停")
            self.state.status = "running"
            if self.state.window_kind:
                self.state.deadline = time.monotonic() + self.state.window_duration
            self._snapshot_required = True
            await self._persist_lobby()
            await self.start_loop()

    # ============================================================ 恢复
    @classmethod
    async def recover(cls, hub: Any = None) -> "GameEngine | None":
        async with SessionLocal() as db:
            row = (await db.execute(
                select(Game).where(Game.status.in_(("lobby", "running", "paused")))
                .order_by(Game.id.desc()).limit(1))).scalars().first()
            if row is None:
                return None
            snap = (await db.execute(
                select(GameSnapshot).where(GameSnapshot.game_id == row.id)
                .order_by(GameSnapshot.sequence_number.desc()).limit(1))).scalars().first()
            if snap is None:
                return None
            st = GameState.from_dict(snap.state)
            engine = cls(state=st, hub=hub)
            events = (await db.execute(
                select(GameEvent).where(
                    GameEvent.game_id == row.id,
                    GameEvent.sequence_number > snap.sequence_number)
                .order_by(GameEvent.sequence_number))).scalars().all()
            for ev in events:
                d = {
                    "seq": ev.sequence_number,
                    "type": ev.type,
                    "actor_seat": ev.actor_seat,
                    "day": ev.day,
                    "night": ev.night,
                    "phase": ev.phase,
                    "payload": ev.payload,
                    "visible_to": ev.visible_to,
                    "ts": 0.0,
                }
                engine.events.append(d)
                engine.state.next_seq = ev.sequence_number + 1
                engine.state.last_seq = ev.sequence_number
                engine._apply_event(engine.state, d)
            st = engine.state
            if st.status in ("running", "paused"):
                st.deadline = time.monotonic() + st.window_duration if st.window_kind else 0.0
                # 回合令牌从历史最大 token 之后继续，避免与已持久化的
                # ClientCommand（ai:{token}:...）碰撞而被幂等去重吞掉
                st.turn_token = await cls._next_token(db, st.game_id)
                st.ai_delay_until = 0.0
            if st.status == "running":
                await engine.start_loop()
            return engine

    @staticmethod
    async def _next_token(db, game_id: int) -> int:
        from sqlalchemy import func, select
        rows = (await db.execute(
            select(ClientCommand.request_id).where(
                ClientCommand.game_id == game_id,
                ClientCommand.request_id.like("ai:%")))).scalars().all()
        max_tok = 0
        for rid in rows:
            try:
                max_tok = max(max_tok, int(rid.split(":")[1]))
            except (ValueError, IndexError):
                continue
        return max_tok + 1
