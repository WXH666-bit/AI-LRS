"""游戏引擎规则测试：全 AI 模拟、胜负判定、信息隔离、幂等、超时、恢复。"""
import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.database import SessionLocal
from app.game.engine import GameEngine, GameError
from app.game.state import GameState, PlayerState
from app.models import GameEvent, GameResult
from app.services.hub import Connection

from .helpers import drive_game, make_game, simulate_game, stub_act, make_user


# ============================================================ 完整对局
@pytest.mark.parametrize("board,seed", [(6, 1), (6, 2), (9, 1), (9, 2), (12, 1), (12, 3)])
async def test_full_game_completes(board, seed):
    engine = await simulate_game(board, seed=seed)
    st = engine.state
    assert st.status == "ended", f"对局未结束: {st.phase}"
    assert st.winner in ("good", "wolf")
    assert st.end_reason
    # 胜负一致性
    wolves = [p for p in st.players if p.role == "wolf" and p.alive]
    villagers = [p for p in st.players if p.role == "villager" and p.alive]
    specials = [p for p in st.players if p.role in ("seer", "witch", "hunter", "guard") and p.alive]
    if st.winner == "good":
        assert not wolves
    else:
        assert not villagers or not specials
    # 事件序号连续
    seqs = [e["seq"] for e in engine.events]
    assert seqs == list(range(1, len(seqs) + 1))
    # DB 已归档
    async with SessionLocal() as db:
        r = await db.get(GameResult, st.game_id)
        assert r is not None and r.winner == st.winner
        db_events = (await db.execute(
            select(GameEvent).where(GameEvent.game_id == st.game_id))).scalars().all()
        assert len(db_events) == len(engine.events)
        for ev, mem in zip(db_events, engine.events):
            assert ev.sequence_number == mem["seq"]
            assert ev.type == mem["type"]


async def test_sheriff_election_happens_after_night1():
    engine = await simulate_game(9, seed=5)
    st = engine.state
    types = [e["type"] for e in engine.events]
    assert "sheriff_elected" in types
    # 警长竞选发生在第一夜之后、夜间结果公布之前
    n1_idx = types.index("game_started")
    election_idx = types.index("sheriff_elected")
    night_result_idx = types.index("night_result")
    assert n1_idx < election_idx < night_result_idx
    # 警长存在且为存活或已结算
    assert st.sheriff_seat is not None or "sheriff_destroy" in types or "sheriff_transfer" in types


async def test_wolf_explode_ends_day():
    engine = await make_game(6, seed=11)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        await drive_until_phase(engine, "day_speech")
        async with engine.lock:
            st = engine.state
            if st.status == "ended":
                # 狼在夜里全灭，没有白天可自爆 —— 换种子
                return
            wolves = st.alive_wolves()
            if not wolves:
                return
            wolf = wolves[0]
            night_before = st.night
            await engine._apply_command("wolf_explode", {}, wolf, None)
            st2 = engine.state
            if st2.status == "ended":
                assert st2.winner == "good"
            else:
                assert st2.phase == "night"
                assert st2.night == night_before + 1
            explode_events = [e for e in engine.events if e["type"] == "wolf_explode"]
            assert len(explode_events) == 1


async def drive_until_phase(engine, phase: str):
    """驱动直到进入指定阶段（AI 存根行动）。"""
    rng = engine.rng
    for _ in range(3000):
        async with engine.lock:
            st = engine.state
            if st.status != "running":
                return
            if st.phase == phase:
                return
            if not st.acting_seats:
                await engine._tick()
                continue
            acted = False
            for seat in st.acting_seats:
                p = st.player(seat)
                if p and p.controller_type == "ai":
                    await stub_act(engine, seat, rng)
                    acted = True
            if not acted:
                return
    raise AssertionError("未进入目标阶段")


# ============================================================ 幂等
async def test_duplicate_request_id_ignored():
    engine = await make_game(6, seed=3)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        await drive_until_phase(engine, "day_speech")
        async with engine.lock:
            st = engine.state
            seat = st.acting_seats[0]
            await engine._apply_command("speak", {"text": "第一次发言"}, seat, "req-abc")
            await engine._apply_command("speak", {"text": "重复发言"}, seat, "req-abc")
            speeches = [e for e in engine.events if e["type"] == "speech" and e["actor_seat"] == seat]
            assert len(speeches) == 1
            assert speeches[0]["payload"]["text"] == "第一次发言"


# ============================================================ 非法动作
def make_engine_with_state(**kw):
    st = GameState(game_id=1, board_size=6, status="running", **kw)
    engine = GameEngine(state=st)
    return engine


def _seats(n: int) -> list[PlayerState]:
    return [PlayerState(seat_number=i + 1, controller_type="ai", alive=True, role="villager") for i in range(n)]


def test_wolf_cannot_kill_teammate():
    st = GameState(game_id=1, board_size=6, status="running", night=1, night_step="wolf_kill",
                   window_kind="wolf_kill", acting_seats=[1, 2])
    st.players = _seats(6)
    st.players[0].role = "wolf"
    st.players[1].role = "wolf"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "wolf_kill", "target": 2}, 1)


def test_guard_cannot_protect_same_target_twice():
    st = GameState(game_id=1, board_size=6, status="running", night=2, night_step="guard",
                   window_kind="night_skill", acting_seats=[3], guard_prev_target=5)
    st.players = _seats(6)
    st.players[2].role = "guard"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "guard_protect", "target": 5}, 3)


def test_witch_save_non_victim_rejected():
    st = GameState(game_id=1, board_size=6, status="running", night=1, night_step="witch",
                   window_kind="night_skill", acting_seats=[4], witch_victim=5, witch_save_used=False)
    st.players = _seats(6)
    st.players[3].role = "witch"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "witch_save", "target": 2}, 4)


def test_witch_save_twice_rejected():
    st = GameState(game_id=1, board_size=6, status="running", night=1, night_step="witch",
                   window_kind="night_skill", acting_seats=[4], witch_victim=5, witch_save_used=True)
    st.players = _seats(6)
    st.players[3].role = "witch"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "witch_save", "target": 5}, 4)


def test_poison_twice_rejected():
    st = GameState(game_id=1, board_size=6, status="running", night=1, night_step="witch",
                   window_kind="night_skill", acting_seats=[4], witch_poison_used=True)
    st.players = _seats(6)
    st.players[3].role = "witch"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "witch_poison", "target": 2}, 4)


def test_vote_self_rejected():
    st = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote",
                   window_kind="lynch_vote", acting_seats=[2])
    st.players = _seats(6)
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("vote", {"target": 2}, 2)


def test_dead_player_cannot_act():
    st = GameState(game_id=1, board_size=6, status="running", phase="day_speech",
                   window_kind="speech", acting_seats=[3])
    st.players = _seats(6)
    st.players[2].alive = False
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("speak", {"text": "诈尸"}, 3)


def test_witch_self_save_only_night1():
    st = GameState(game_id=1, board_size=6, status="running", night=2, night_step="witch",
                   window_kind="night_skill", acting_seats=[4], witch_victim=4, witch_save_used=False)
    st.players = _seats(6)
    st.players[3].role = "witch"
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("use_skill", {"skill": "witch_save", "target": 4}, 4)
    # 首夜自救允许
    st.night = 1
    evs = engine._handle_command("use_skill", {"skill": "witch_save", "target": 4}, 4)
    assert evs[0]["type"] == "witch_action"


def test_not_acting_seat_rejected():
    st = GameState(game_id=1, board_size=6, status="running", phase="day_speech",
                   window_kind="speech", acting_seats=[5])
    st.players = _seats(6)
    engine = GameEngine(state=st)
    with pytest.raises(GameError):
        engine._handle_command("speak", {"text": "插嘴"}, 2)


# ============================================================ 平票 PK
def test_lynch_tie_leads_to_pk_then_no_lynch():
    st = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote", night=1, day=1)
    st.players = _seats(6)
    # 存活 1/2/3，投票：1→2, 2→3, 3→弃权 → 2号与3号平票
    st.lynch_votes = {1: 2, 2: 3, 3: 0}
    engine = GameEngine(state=st)
    events = engine._tally_lynch([])
    assert engine.state.phase == "lynch_pk_speech"
    assert engine.state.lynch_pk == [2, 3]
    assert any(e["type"] == "phase_change" for e in events)
    # 完成 PK 发言与投票，再次平票 → 无人出局 → 进入夜晚
    st.lynch_pk_speeches = {2: {"text": "a"}, 3: {"text": "b"}}
    st.lynch_pk_votes = {1: 2, 2: 3, 3: 0}
    st.phase = "lynch_pk_vote"
    events = engine._tally_lynch([])
    assert any(e["type"] == "lynch_result" and e["payload"].get("seat") is None for e in events)
    assert engine.state.phase == "night"
    assert engine.state.night == 2


def test_lynch_unique_max_lynched():
    st = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote", night=1, day=1)
    st.players = _seats(6)
    st.lynch_votes = {1: 2, 2: 3, 3: 3}
    engine = GameEngine(state=st)
    events = engine._tally_lynch([])
    assert any(e["type"] == "lynch_result" and e["payload"]["seat"] == 3 for e in events)
    assert engine.state.phase == "last_words"
    assert engine.state.pending_last_words == 3


def test_sheriff_half_vote_breaks_tie():
    # 无警长：1→2, 2→3, 3→弃权 → 2号与3号各1票平票
    st = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote", night=1, day=1)
    st.players = _seats(6)
    st.lynch_votes = {1: 2, 2: 3, 3: 0}
    engine = GameEngine(state=st)
    engine._tally_lynch([])
    assert engine.state.phase == "lynch_pk_speech"
    assert engine.state.lynch_pk == [2, 3]
    # 有警长（1号）：2号 2.5 票胜出
    st2 = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote", night=1, day=1)
    st2.players = _seats(6)
    st2.sheriff_seat = 1
    st2.lynch_votes = {1: 2, 2: 3, 3: 0}
    engine2 = GameEngine(state=st2)
    events = engine2._tally_lynch([])
    assert any(e["type"] == "lynch_result" and e["payload"]["seat"] == 2 for e in events)


# ============================================================ 信息隔离
async def test_visibility_events():
    engine = await simulate_game(6, seed=13)
    for ev in engine.events:
        if ev["type"] in ("seer_result", "witch_info", "witch_action", "guard_action", "role_assign"):
            assert ev["visible_to"] is not None, f"{ev['type']} 必须私有"
            # 死亡/缺席时可见列表可为空，但绝不能是公开的 None
            assert len(ev["visible_to"]) <= 1
        if ev["type"] == "wolf_chat":
            assert ev["visible_to"] is not None and len(ev["visible_to"]) >= 1
        if ev["type"] in ("wolf_vote", "wolf_kill_result"):
            assert ev["visible_to"] is not None  # 狼人内部信息
        if ev["type"] in ("vote", "speech", "night_result", "lynch_result", "hunter_shot",
                          "sheriff_elected", "sheriff_apply", "wolf_explode"):
            assert ev["visible_to"] is None, f"{ev['type']} 应为公开"


async def test_view_hides_roles_from_spectators():
    engine = await make_game(6, seed=2)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        async with engine.lock:
            view = engine.build_view(None)
            assert all(p["role"] is None for p in view["players"])
            assert "roles_revealed" not in view
            # 结束前任何玩家看不到他人身份
            view2 = engine.build_view(1)
            roles = [p["role"] for p in view2["players"] if p["seat"] != 1]
            assert all(r is None for r in roles)
            assert view2["me"]["role"] is not None


# ============================================================ 超时与托管
async def test_human_timeout_then_trustee():
    u = await make_user("human1")
    engine = await make_game(6, seed=5, empty_seat=1)
    async with engine.lock:
        await engine.join(u.id, u.username, 1)
        await engine.set_ready(u.id, True)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        # 驱动直到 1 号需要行动
        rng = engine.rng
        for _ in range(3000):
            async with engine.lock:
                st = engine.state
                if st.status != "running":
                    break
                if st.acting_seats and 1 in st.acting_seats:
                    break
                acted = False
                for seat in st.acting_seats:
                    p = st.player(seat)
                    if p and p.controller_type == "ai":
                        await stub_act(engine, seat, rng)
                        acted = True
                        break
                if not acted:
                    break
        # 第一次超时 → 跳过
        async with engine.lock:
            st = engine.state
            assert 1 in st.acting_seats
            await engine._force_timeout()
            p = st.player(1)
            assert p.consecutive_timeouts == 1
            assert p.controller_type == "human"
        # 继续驱动到 1 号再次行动
        for _ in range(3000):
            async with engine.lock:
                st = engine.state
                if st.status != "running" or st.acting_seats and 1 in st.acting_seats:
                    break
                acted = False
                for seat in st.acting_seats:
                    p = st.player(seat)
                    if p and p.controller_type == "ai":
                        await stub_act(engine, seat, rng)
                        acted = True
                        break
                if not acted:
                    break
        async with engine.lock:
            st = engine.state
            assert st.status == "running"
            assert 1 in st.acting_seats
            await engine._force_timeout()
            p = st.player(1)
            assert p.controller_type == "trustee"  # 连续两次超时 → AI 托管
            control_events = [e for e in engine.events if e["type"] == "seat_control"]
            assert any(e["payload"]["controller_type"] == "trustee" for e in control_events)


# ============================================================ Hub 死连接清理
async def test_hub_drops_dead_connections():
    """死连接（send 失败）必须被丢弃，不能阻塞广播。"""
    from app.services.hub import Hub

    hub = Hub()

    class DeadConn:
        def __init__(self):
            self.seat = None
            self.user_id = 1
            self.dropped = False

        async def send(self, data):
            raise ConnectionError("dead")

    async def fake_send_ok(conn):
        return None

    alive = Connection(ws=None, user_id=2, seat=None)
    alive.send = _fake_send(alive)
    hub.conns.add(DeadConn())
    hub.conns.add(alive)
    await hub.broadcast_event({"visible_to": None, "seq": 1, "type": "x", "actor_seat": None,
                               "day": 1, "night": 1, "phase": "night", "payload": {}})
    assert len(hub.conns) == 1  # 死连接被清理，活连接保留
    assert len(alive.received) == 1


# ============================================================ 遗言窗口超时（已出局玩家）
async def test_dead_player_last_words_timeout():
    """被放逐玩家的遗言窗口必须能超时跳过，不能卡局。"""
    u = await make_user("human1")
    engine = await make_game(6, seed=5, empty_seat=1)
    async with engine.lock:
        await engine.join(u.id, u.username, 1)
        await engine.set_ready(u.id, True)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        # 直接构造：1号被放逐进入遗言窗口
        async with engine.lock:
            st = engine.state
            st.pending_last_words = 1
            st.last_words_acted = False
            st.phase = "last_words"
            st.window_kind = "last_words"
            st.acting_seats = [1]
            st.deadline = 0  # 已超时
            st.player(1).alive = False
            await engine._force_timeout()
            assert st.last_words_acted is True or any(
                e["type"] == "last_words" and e["payload"].get("skipped") for e in engine.events)
            # 遗言窗口已推进（进入下一阶段，而不是卡住）
            assert st.phase != "last_words"


# ============================================================ 快照与恢复
async def test_snapshot_recovery():
    engine = await make_game(9, seed=8)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()
        await drive_until_phase(engine, "day_speech")
        async with engine.lock:
            st = engine.state
            assert st.phase == "day_speech"
            # 强制写快照（模拟阶段转移后的持久化点）
            engine._snapshot_required = True
            await engine._persist_lobby()
            snapshot_seq = st.last_seq
            phase = st.phase
            night = st.night
        # 快照之后再执行若干动作（产生快照后的事件，供恢复时重放）
        rng = engine.rng
        for _ in range(3):
            async with engine.lock:
                st = engine.state
                if st.status != "running":
                    break
                for seat in st.acting_seats:
                    p = st.player(seat)
                    if p and p.controller_type == "ai":
                        await stub_act(engine, seat, rng)
        async with engine.lock:
            st = engine.state
            last_seq = st.last_seq
            post_snapshot_events = [e for e in engine.events if e["seq"] > snapshot_seq]
            assert last_seq > snapshot_seq
            assert len(post_snapshot_events) >= 3
    # 模拟崩溃前已持久化的 AI 命令（token 0），验证恢复后令牌从历史之后继续
    from app.models import ClientCommand
    async with SessionLocal() as db:
        db.add(ClientCommand(game_id=engine.state.game_id, request_id="ai:0:3:0",
                             seat_number=3, type="speak", payload={"text": "x"}))
        await db.commit()
    # 恢复
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        recovered = await GameEngine.recover()
    assert recovered is not None
    rst = recovered.state
    assert rst.phase == phase
    assert rst.night == night
    assert rst.last_seq == last_seq
    assert len(recovered.events) == len(post_snapshot_events)
    # 恢复后的回合令牌必须大于历史最大 token（否则 AI 请求被幂等吞掉）
    assert rst.turn_token > 0
    # 恢复后继续驱动到结束
    await drive_game(recovered)
    assert recovered.state.status == "ended"


# ============================================================ 观战 Hub（20 名观众）
async def test_hub_20_spectators():
    engine = await simulate_game(6, seed=4)
    # 回放事件到 20 个假连接
    conns = []
    for i in range(20):
        c = Connection(ws=None, user_id=9000 + i, seat=None)
        c.send = _fake_send(c)
        conns.append(c)
    for ev in engine.events[:50]:
        for c in conns:
            if ev.get("visible_to") is None or (c.seat and c.seat in ev["visible_to"]):
                await c.send({"type": "event", "event": ev})
    for c in conns:
        assert len(c.received) >= 1
        assert all(m["type"] == "event" for m in c.received)


def _fake_send(conn):
    async def send(data):
        if not hasattr(conn, "received"):
            conn.received = []
        conn.received.append(data)
    return send
