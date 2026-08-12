"""AI 临时流式消息的权限与回合令牌测试。"""

from unittest.mock import AsyncMock

import pytest

from app.game.engine import GameEngine
from app.game.state import GameState, PlayerState
from app.services.hub import Connection, Hub


def _fake_send(conn):
    async def send(data):
        if not hasattr(conn, "received"):
            conn.received = []
        conn.received.append(data)

    return send


@pytest.mark.asyncio
async def test_hub_stream_broadcast_filters_by_seat():
    hub = Hub()
    wolf = Connection(ws=None, user_id=1, seat=1)
    teammate = Connection(ws=None, user_id=2, seat=2)
    villager = Connection(ws=None, user_id=3, seat=3)
    for conn in (wolf, teammate, villager):
        conn.send = _fake_send(conn)
        hub.conns.add(conn)

    await hub.broadcast_stream(
        {
            "stream_id": "ai:1:2:1",
            "actor_seat": 1,
            "window_kind": "wolf_chat",
            "text": "只给狼队看",
            "status": "chunk",
        },
        visible_to=[1, 2],
    )

    assert wolf.received[0]["type"] == "ai_stream"
    assert teammate.received[0]["type"] == "ai_stream"
    assert not hasattr(villager, "received")


@pytest.mark.asyncio
async def test_engine_stream_rejects_stale_turn_token_without_event():
    state = GameState(game_id=1, board_size=6, status="running", phase="day_speech")
    state.players = [PlayerState(seat_number=1, controller_type="ai", alive=True, role="villager")]
    state.window_kind = "speech"
    state.acting_seats = [1]
    state.turn_token = 4
    engine = GameEngine(state=state, hub=Hub())
    engine.hub.broadcast_stream = AsyncMock()

    assert await engine.emit_ai_stream(1, 3, "stream-old", "旧片段", "chunk") is False
    engine.hub.broadcast_stream.assert_not_awaited()
    assert engine.events == []

    assert await engine.emit_ai_stream(1, 4, "stream-new", "新片段", "chunk") is True
    engine.hub.broadcast_stream.assert_awaited_once()
