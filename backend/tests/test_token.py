"""回归测试：turn_token 必须跨 phase_change 持久化，避免 AI 请求令牌碰撞。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.game.engine import GameEngine
from app.game.state import GameState, PlayerState
from app.database import SessionLocal
from app.models import Game, User


@pytest.fixture
async def engine_with_row():
    async with SessionLocal() as db:
        u = User(username="host", password_hash="x", role="user")
        db.add(u)
        await db.commit()
        await db.refresh(u)
        row = Game(board_size=6, status="running", phase="day_speech", created_by=u.id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        game_id = row.id
    st = GameState(game_id=game_id, board_size=6, status="running", phase="day_speech")
    st.players = [PlayerState(seat_number=i + 1, controller_type="ai", alive=True, role="villager")
                  for i in range(6)]
    return GameEngine(state=st)


async def test_turn_token_survives_phase_change(engine_with_row):
    """phase_change 重建状态后 turn_token 保持递增。"""
    engine = engine_with_row
    async with engine.lock:
        evs = engine._open_window("speech", [1], 45)
        t1 = engine.state.turn_token
        assert t1 == 1
        await engine._emit(evs)  # 应用 phase_change（重建状态）
        assert engine.state.turn_token == 1, "phase_change 重建后 turn_token 被重置"

        # 下一个窗口 token 必须递增（AI request_id 依赖此唯一性）
        await engine._emit(engine._open_window("speech", [2], 45))
        assert engine.state.turn_token == 2

    # 提交过期令牌（token=1，当前窗口 token=2）→ 应被丢弃
    await engine.commit_ai(1, 1, {"action_type": "speak", "speech": "过期发言"})
    speeches = [e for e in engine.events if e["type"] == "speech"]
    assert len(speeches) == 0, "过期令牌的结果必须被丢弃"

    # 当前令牌提交 → 生效
    await engine.commit_ai(2, 2, {"action_type": "speak", "speech": "有效发言"})
    speeches = [e for e in engine.events if e["type"] == "speech"]
    assert len(speeches) == 1
    assert speeches[0]["payload"]["text"] == "有效发言"
