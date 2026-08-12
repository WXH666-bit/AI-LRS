"""依赖分组调度的回归测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.game.engine import GameEngine
from app.game.state import GameState, PlayerState

from .helpers import make_game


def _players(roles: dict[int, str], count: int = 6) -> list[PlayerState]:
    return [
        PlayerState(
            seat_number=seat,
            controller_type="ai",
            alive=True,
            role=roles.get(seat, "villager"),
        )
        for seat in range(1, count + 1)
    ]


def test_lynch_vote_window_contains_all_alive_voters():
    state = GameState(game_id=1, board_size=6, status="running", phase="lynch_vote")
    state.players = _players({}, count=4)
    engine = GameEngine(state=state)

    kind, seats, _duration = engine._next_window()

    assert kind == "lynch_vote"
    assert seats == [1, 2, 3, 4]


def test_parallel_vote_window_waits_for_every_voter():
    state = GameState(
        game_id=1,
        board_size=6,
        status="running",
        phase="lynch_vote",
        window_kind="lynch_vote",
        acting_seats=[1, 2, 3],
    )
    state.players = _players({}, count=3)
    state.lynch_votes = {1: 2}
    engine = GameEngine(state=state)

    assert engine._window_complete() is False

    state.lynch_votes.update({2: 3, 3: 0})
    assert engine._window_complete() is True


def test_completed_parallel_actor_cannot_be_scheduled_again():
    state = GameState(
        game_id=1,
        board_size=6,
        status="running",
        phase="lynch_vote",
        window_kind="lynch_vote",
        acting_seats=[1, 2],
    )
    state.players = _players({}, count=2)
    state.lynch_votes = {1: 2}
    engine = GameEngine(state=state)

    assert engine._pending_window_seats() == [2]
    assert engine.legal_actions_for(1) == []
    assert engine.build_view(1)["game"]["acting_seats"] == [2]


def test_new_night_starts_with_serial_wolf_chat():
    state = GameState(game_id=1, board_size=6, status="running", night=0, phase="night")
    state.players = _players({1: "wolf", 2: "wolf"})
    engine = GameEngine(state=state)

    engine._start_night([])
    kind, seats, _duration = engine._next_window()

    assert state.night_step == "wolf_chat"
    assert kind == "wolf_chat"
    assert seats == [1]


@pytest.mark.asyncio
async def test_first_night_starts_with_serial_wolf_chat():
    engine = await make_game(6, seed=1)
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        async with engine.lock:
            await engine.start_game()

    assert engine.state.night_step == "wolf_chat"
    assert engine.state.window_kind == "wolf_chat"


def test_starting_a_new_night_clears_previous_wolf_chat():
    state = GameState(game_id=1, board_size=6, status="running", night=1, phase="night")
    state.players = _players({1: "wolf", 2: "wolf"})
    state.wolf_chat = [{"night": 1, "seat": 1, "text": "旧消息"}]
    state.wolf_chat_done = [1, 2]
    engine = GameEngine(state=state)

    engine._start_night([])

    assert state.wolf_chat == []
    assert state.wolf_chat_done == []


def test_wolf_chat_message_is_private_and_unlocks_next_wolf_only():
    state = GameState(
        game_id=1,
        board_size=6,
        status="running",
        phase="night",
        night=1,
        night_step="wolf_chat",
        window_kind="wolf_chat",
        acting_seats=[1],
    )
    state.players = _players({1: "wolf", 2: "wolf"})
    engine = GameEngine(state=state)

    events = engine._handle_command("wolf_chat", {"text": "先观察3号"}, 1)

    assert events[0]["type"] == "wolf_chat"
    assert events[0]["visible_to"] == [1, 2]


def test_night_skills_window_contains_independent_special_roles():
    state = GameState(
        game_id=1,
        board_size=12,
        status="running",
        phase="night",
        night=1,
        night_step="skills",
    )
    state.players = _players({1: "wolf", 2: "guard", 3: "seer", 4: "witch"}, count=6)
    engine = GameEngine(state=state)

    kind, seats, _duration = engine._next_window()

    assert kind == "night_skill"
    assert seats == [2, 3, 4]


def test_parallel_night_skills_wait_for_each_role():
    state = GameState(
        game_id=1,
        board_size=12,
        status="running",
        phase="night",
        night=1,
        night_step="skills",
        window_kind="night_skill",
        acting_seats=[2, 3, 4],
    )
    state.players = _players({2: "guard", 3: "seer", 4: "witch"}, count=6)
    state.guard_acted = True
    engine = GameEngine(state=state)

    assert engine._window_complete() is False

    state.seer_acted = True
    state.witch_acted = True
    assert engine._window_complete() is True
