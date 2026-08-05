"""AI 调用与失败兜底回归测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.adapters import test_connection as run_connection_test
from app.ai.prompts import build_prompts
import app.ai.orchestrator as ai_orchestrator
from app.game.engine import GameEngine
from app.models import ModelConfig
from app.game.state import GameState, PlayerState


def _speech_engine() -> GameEngine:
    state = GameState(game_id=1, board_size=6, status="running", phase="day_speech")
    state.players = [
        PlayerState(seat_number=1, controller_type="ai", alive=True, role="villager"),
    ]
    state.window_kind = "speech"
    state.acting_seats = [1]
    return GameEngine(state=state)


def test_ai_prompt_lists_dead_seat_without_private_player_state():
    state = GameState(game_id=1, board_size=6, status="running", phase="day_speech")
    state.players = [
        PlayerState(seat_number=1, controller_type="ai", alive=True, role="villager"),
        PlayerState(seat_number=6, controller_type="ai", alive=False, role="wolf"),
    ]
    state.window_kind = "speech"
    state.acting_seats = [1]
    engine = GameEngine(state=state)

    _, user_prompt = build_prompts(engine, 1, engine.build_ai_request(1), None)

    assert "- 已出局：6号" in user_prompt
    assert "PlayerState" not in user_prompt
    assert "role='wolf'" not in user_prompt


def test_failed_ai_speech_uses_non_empty_fallback_speech():
    engine = _speech_engine()

    commands = engine._ai_result_to_commands(1, None)

    assert commands[0][0] == "speak"
    assert commands[0][1]["text"]


def test_explicit_ai_pass_remains_a_pass():
    engine = _speech_engine()

    commands = engine._ai_result_to_commands(1, {"action_type": "pass"})

    assert commands == [("pass", {})]


def test_ai_response_budget_is_compact_for_game_turns():
    budget_fn = getattr(ai_orchestrator, "_response_token_budget", None)
    assert budget_fn is not None
    assert budget_fn("speech", 2048) == 512
    assert budget_fn("lynch_vote", 2048) == 256
    assert budget_fn("speech", 128) == 128


@pytest.mark.asyncio
async def test_connection_rejects_empty_model_response():
    cfg = ModelConfig(
        display_name="test",
        protocol="openai_compatible",
        base_url="https://test.local/v1",
        model_name="test-model",
        encrypted_api_key="",
    )

    with patch("app.ai.adapters.call_model", new=AsyncMock(return_value=("", {}))):
        result = await run_connection_test(cfg, "")

    assert result["ok"] is False
    assert "空" in result["message"]
