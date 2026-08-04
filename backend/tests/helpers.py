"""测试辅助：建引擎、AI 存根驱动、断言。"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.database import SessionLocal
from app.game.engine import SPEECH_WINDOWS, VOTE_WINDOWS, GameEngine, GameError
from app.game.state import GameState, PlayerState
from app.models import AIPersona, Game, ModelConfig, User
from app.security import encrypt_secret


async def make_model_config(protocol: str = "openai_compatible") -> ModelConfig:
    async with SessionLocal() as db:
        m = ModelConfig(
            display_name="test-model",
            protocol=protocol,
            base_url="https://test.local/v1",
            model_name="test-model",
            encrypted_api_key=encrypt_secret("sk-test"),
            enabled=True,
            is_default_fallback=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return m


async def make_user(username: str = "u1") -> User:
    async with SessionLocal() as db:
        u = User(username=username, password_hash="x", role="user")
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


async def make_game(board_size: int, seed: int = 1, empty_seat: int | None = None) -> GameEngine:
    """创建带完整座位的引擎（大厅状态），AI 填满；empty_seat 指定的座位留空供真人加入。"""
    await make_model_config()
    await make_persona()
    u = await make_user("host")
    async with SessionLocal() as db:
        row = Game(board_size=board_size, status="lobby", phase="lobby", created_by=u.id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        game_id = row.id
    st = GameState(game_id=game_id, board_size=board_size)
    for seat in range(1, board_size + 1):
        st.players.append(PlayerState(seat_number=seat, controller_type="empty"))
    engine = GameEngine(state=st)
    engine.rng.seed(seed)
    engine._snapshot_required = True
    await engine._persist_lobby()
    # 填满 AI（保留 empty_seat 空位）
    async with engine.lock:
        await engine.ai_fill(None, None)
        if empty_seat:
            p = engine.state.player(empty_seat)
            if p and p.controller_type == "ai":
                p.controller_type = "empty"
                p.user_id = None
                p.model_config_id = None
                p.persona_id = None
                p.persona_name = None
                engine._players_dirty = True
                engine._snapshot_required = True
                await engine._persist_lobby()
    return engine


async def make_persona() -> AIPersona:
    async with SessionLocal() as db:
        p = AIPersona(name="测试人格", speaking_style="简短", aggression=3)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p


# ------------------------------------------------------------------ 驱动
async def stub_act(engine: GameEngine, seat: int, rng) -> None:
    """AI 存根：按合法动作表选择确定性动作。"""
    st = engine.state
    kind = st.window_kind or ""
    acts = engine.legal_actions_for(seat)
    targets = engine.legal_targets_for(seat)

    if kind in SPEECH_WINDOWS:
        text = f"我是{seat}号，简单说两句。"
        await engine._apply_command("speak", {"text": text}, seat, None)
    elif kind in VOTE_WINDOWS:
        # 偏向确定性：多数投同一目标以加速收敛，偶尔随机/弃权以覆盖平票路径
        if targets and rng.random() < 0.85:
            await engine._apply_command("vote", {"target": targets[0]["seat"]}, seat, None)
        elif targets and rng.random() < 0.7:
            t = rng.choice(targets)["seat"]
            await engine._apply_command("vote", {"target": t}, seat, None)
        else:
            await engine._apply_command("vote", {"target": 0}, seat, None)
    elif kind == "election_apply":
        r = rng.random()
        if r < 0.4:
            await engine._apply_command("sheriff_action", {"action": "apply"}, seat, None)
        else:
            await engine._apply_command("sheriff_action", {"action": "pass"}, seat, None)
    elif kind == "wolf_kill":
        if targets and rng.random() < 0.9:
            await engine._apply_command("use_skill", {"skill": "wolf_kill", "target": targets[0]["seat"]}, seat, None)
        else:
            await engine._apply_command("use_skill", {"skill": "wolf_kill", "target": 0}, seat, None)
    elif kind == "night_skill":
        step = st.night_step
        if step == "guard":
            if targets:
                await engine._apply_command("use_skill", {"skill": "guard_protect", "target": targets[0]["seat"]}, seat, None)
            else:
                await engine._apply_command("use_skill", {"skill": "guard_protect", "target": None}, seat, None)
        elif step == "seer":
            if targets:
                await engine._apply_command("use_skill", {"skill": "seer_check", "target": targets[0]["seat"]}, seat, None)
            else:
                await engine._apply_command("use_skill", {"skill": "seer_check", "target": None}, seat, None)
        elif step == "witch":
            save = [t for t in targets if t.get("kind") == "save"]
            poison = [t for t in targets if t.get("kind") == "poison"]
            if save and rng.random() < 0.7:
                await engine._apply_command("use_skill", {"skill": "witch_save", "target": save[0]["seat"]}, seat, None)
            elif poison and rng.random() < 0.5:
                await engine._apply_command("use_skill", {"skill": "witch_poison", "target": rng.choice(poison)["seat"]}, seat, None)
            else:
                await engine._apply_command("pass", {}, seat, None)
    elif kind == "hunter_shot":
        if targets and rng.random() < 0.5:
            await engine._apply_command("use_skill", {"skill": "hunter_shot", "target": targets[0]["seat"]}, seat, None)
        else:
            await engine._apply_command("use_skill", {"skill": "hunter_shot", "target": None}, seat, None)
    elif kind == "sheriff_transfer":
        if targets:
            await engine._apply_command("sheriff_action", {"action": "transfer", "target": targets[0]["seat"]}, seat, None)
        else:
            await engine._apply_command("sheriff_action", {"action": "destroy"}, seat, None)
    else:
        await engine._apply_command("pass", {}, seat, None)


async def drive_game(engine: GameEngine, max_actions: int = 5000) -> None:
    """驱动整局：每个窗口让所有 AI 行动，直到对局结束或超过上限。"""
    rng = engine.rng
    for _ in range(max_actions):
        async with engine.lock:
            st = engine.state
            if st.status != "running":
                return
            if not st.acting_seats:
                # 无窗口时触发 tick 推进（一般由命令触发，这里兜底）
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
    raise AssertionError(f"对局未在 {max_actions} 次行动内结束")


async def simulate_game(board_size: int, seed: int = 1) -> GameEngine:
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        engine = await make_game(board_size, seed=seed)
        async with engine.lock:
            await engine.start_game()
        await drive_game(engine)
    return engine
