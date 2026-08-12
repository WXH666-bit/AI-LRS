"""AI 调用与失败兜底回归测试。"""

from unittest.mock import AsyncMock, patch
import asyncio

import pytest

from app.ai.adapters import test_connection as run_connection_test
from app.ai.prompts import build_prompts, format_history
import app.ai.orchestrator as ai_orchestrator
from app.database import SessionLocal
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
    assert budget_fn("speech", 2048) == 320
    assert budget_fn("wolf_chat", 2048) == 160
    assert budget_fn("lynch_vote", 2048) == 128
    assert budget_fn("speech", 128) == 128


@pytest.mark.asyncio
async def test_retry_reuses_same_model_without_fallback(monkeypatch):
    cfg = ModelConfig(
        id=11,
        display_name="primary",
        protocol="openai_compatible",
        base_url="https://primary.local/v1",
        model_name="primary-model",
        encrypted_api_key="",
        enabled=True,
        is_default_fallback=False,
    )
    calls = []

    async def fake_call(model_cfg, api_key, system, user, max_tokens=None):
        calls.append((model_cfg.id, model_cfg.model_name, model_cfg.base_url))
        if len(calls) == 1:
            raise ai_orchestrator.ModelCallError("超时", kind="timeout")
        return '{"action_type":"pass"}', {}

    monkeypatch.setattr(ai_orchestrator, "call_model", fake_call)
    monkeypatch.setattr(ai_orchestrator.settings, "ai_max_retries", 1)
    orchestrator = ai_orchestrator.AIOrchestrator()

    result, error_kind, _error_msg, _usage = await orchestrator._call_with_retry(
        cfg, "", "system", "user", max_tokens=128)

    assert result == {"action_type": "pass"}
    assert error_kind == ""
    assert calls == [(11, "primary-model", "https://primary.local/v1")] * 2


@pytest.mark.asyncio
async def test_stream_retry_uses_same_model_and_forwards_deltas(monkeypatch):
    cfg = ModelConfig(
        id=12,
        display_name="stream-primary",
        protocol="openai_compatible",
        base_url="https://primary.local/v1",
        model_name="primary-model",
        encrypted_api_key="",
        enabled=True,
    )
    calls = []
    deltas = []

    async def fake_stream(model_cfg, api_key, system, user, on_delta, max_tokens=None):
        calls.append(model_cfg.id)
        await on_delta('{"action_type":"speak","speech":"你好')
        if len(calls) == 1:
            raise ai_orchestrator.ModelCallError("流式超时", kind="timeout")
        await on_delta('，我是1号"}')
        return '{"action_type":"speak","speech":"你好，我是1号"}', {}

    async def collect(delta):
        deltas.append(delta)

    monkeypatch.setattr(ai_orchestrator, "call_model_stream", fake_stream)
    monkeypatch.setattr(ai_orchestrator.settings, "ai_max_retries", 1)
    result, error_kind, _error_msg, _usage = await ai_orchestrator.AIOrchestrator()._call_with_retry(
        cfg, "", "system", "user", max_tokens=128, on_delta=collect)

    assert result == {"action_type": "speak", "speech": "你好，我是1号"}
    assert error_kind == ""
    assert calls == [12, 12]
    assert deltas == [
        '{"action_type":"speak","speech":"你好',
        '{"action_type":"speak","speech":"你好',
        '，我是1号"}',
    ]


@pytest.mark.asyncio
async def test_retry_count_is_capped_at_two_retries(monkeypatch):
    cfg = ModelConfig(
        id=13,
        display_name="retry-primary",
        protocol="openai_compatible",
        base_url="https://primary.local/v1",
        model_name="primary-model",
        encrypted_api_key="",
    )
    calls = 0

    async def always_timeout(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise ai_orchestrator.ModelCallError("超时", kind="timeout")

    monkeypatch.setattr(ai_orchestrator, "call_model", always_timeout)
    monkeypatch.setattr(ai_orchestrator.settings, "ai_max_retries", 99)
    result, error_kind, _error_msg, _usage = await ai_orchestrator.AIOrchestrator()._call_with_retry(
        cfg, "", "system", "user", max_tokens=128
    )

    assert result is None
    assert error_kind == "timeout"
    assert calls == 3


@pytest.mark.asyncio
async def test_run_ai_turn_streams_speech_before_committing(monkeypatch):
    cfg = ModelConfig(
        display_name="stream-primary",
        protocol="openai_compatible",
        base_url="https://primary.local/v1",
        model_name="primary-model",
        encrypted_api_key="encrypted",
        max_output_tokens=512,
        enabled=True,
    )
    async with SessionLocal() as db:
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)

    state = GameState(game_id=1, board_size=6, status="running", phase="day_speech")
    state.turn_token = 7
    state.players = [
        PlayerState(
            seat_number=1,
            controller_type="ai",
            alive=True,
            role="villager",
            model_config_id=cfg.id,
        )
    ]
    state.window_kind = "speech"
    state.acting_seats = [1]

    class FakeEngine:
        def __init__(self):
            self.state = state
            self.lock = asyncio.Lock()
            self._ai_inflight = {1}
            self.stream_updates = []
            self.committed = None

        def build_ai_request(self, _seat):
            return {"window_kind": "speech", "legal_actions": [], "legal_targets": []}

        async def emit_ai_stream(self, seat, token, stream_id, text, status):
            self.stream_updates.append((seat, token, stream_id, text, status))
            return True

        async def commit_ai(self, seat, token, result):
            self.committed = (seat, token, result)

    fake_engine = FakeEngine()

    async def fake_stream(_cfg, _key, _system, _user, on_delta, max_tokens=None):
        assert max_tokens == 320
        await on_delta('{"action_type":"speak","speech":"先')
        await on_delta('发言"}')
        return '{"action_type":"speak","speech":"先发言"}', {}

    monkeypatch.setattr(ai_orchestrator, "call_model_stream", fake_stream)
    monkeypatch.setattr(ai_orchestrator, "build_prompts", lambda *_args: ("system", "user"))
    monkeypatch.setattr(ai_orchestrator, "decrypt_secret", lambda _value: "key")
    monkeypatch.setattr(ai_orchestrator.settings, "ai_max_retries", 0)
    monkeypatch.setattr(ai_orchestrator.AIOrchestrator, "_log_call", AsyncMock())

    await ai_orchestrator.AIOrchestrator().run_ai_turn(fake_engine, 1, 7)

    assert [item[3] for item in fake_engine.stream_updates if item[4] == "chunk"] == ["先", "发言"]
    assert fake_engine.stream_updates[-1][4] == "complete"
    assert fake_engine.committed == (1, 7, {"action_type": "speak", "speech": "先发言"})


@pytest.mark.asyncio
async def test_disabled_selected_model_does_not_resolve_to_fallback():
    primary = ModelConfig(
        id=1,
        display_name="disabled-primary",
        protocol="openai_compatible",
        base_url="https://primary.local/v1",
        model_name="primary-model",
        encrypted_api_key="",
        enabled=False,
        is_default_fallback=False,
    )
    fallback = ModelConfig(
        id=2,
        display_name="fallback",
        protocol="openai_compatible",
        base_url="https://fallback.local/v1",
        model_name="fallback-model",
        encrypted_api_key="",
        enabled=True,
        is_default_fallback=True,
    )
    async with ai_orchestrator.SessionLocal() as db:
        db.add_all([primary, fallback])
        await db.commit()
        await db.refresh(primary)

    resolved = await ai_orchestrator.AIOrchestrator()._resolve_config(primary.id)

    assert resolved is None


def test_prompt_history_keeps_current_day_speeches_but_trims_old_noise():
    state = GameState(
        game_id=1,
        board_size=6,
        status="running",
        phase="day_speech",
        night=3,
        day=3,
    )
    state.players = [
        PlayerState(seat_number=1, controller_type="ai", alive=True, role="villager"),
    ]
    engine = GameEngine(state=state)
    engine.events = [
        {
            "seq": i,
            "type": "speech",
            "actor_seat": 1,
            "day": 1,
            "night": 1,
            "phase": "day_speech",
            "payload": {"text": f"old-noise-{i}"},
            "visible_to": None,
        }
        for i in range(1, 40)
    ]
    engine.events.extend(
        {
            "seq": 100 + i,
            "type": "speech",
            "actor_seat": 1,
            "day": 3,
            "night": 3,
            "phase": "day_speech",
            "payload": {"text": f"current-speech-{i}"},
            "visible_to": None,
        }
        for i in range(1, 8)
    )

    history = format_history(engine, 1, limit=4)

    for i in range(1, 8):
        assert f"current-speech-{i}" in history
    assert "old-noise-1" not in history


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
