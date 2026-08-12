"""AI 编排器：锁定构建请求 → 释放锁调用模型 → 重新加锁校验回合令牌 → 提交。

模型调用期间不持有游戏状态锁；过期结果（阶段已变）直接丢弃。
"""
import asyncio
import json
import logging
import re
import time

from ..config import settings
from ..database import SessionLocal
from ..models import AIPersona, ModelCallLog, ModelConfig
from ..security import decrypt_secret
from .adapters import ModelCallError, call_model, call_model_stream, parse_ai_json
from .prompts import build_prompts

logger = logging.getLogger("game.ai")

_SPEECH_WINDOWS = frozenset({
    "speech", "election_speak", "election_pk_speak", "lynch_pk_speak", "last_words",
})


def _response_token_budget(window_kind: str | None, configured: int) -> int:
    """限制单回合输出，避免长回复超时或在 JSON 中途被截断。"""
    if window_kind in _SPEECH_WINDOWS:
        ceiling = 320
    elif window_kind == "wolf_chat":
        ceiling = 160
    else:
        ceiling = 128
    return max(64, min(configured or ceiling, ceiling))


def _extract_json_string_field(raw: str, field: str) -> str:
    """从尚未闭合的 JSON 中提取可展示的字符串字段。"""
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"', raw)
    if not match:
        return ""
    start = match.end()
    escaped = False
    end = len(raw)
    for index in range(start, len(raw)):
        char = raw[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == '"':
            end = index
            break
    fragment = raw[start:end]
    try:
        return json.loads(f'"{fragment}"')
    except json.JSONDecodeError:
        return fragment.replace('\\"', '"').replace("\\n", "\n")


class AIOrchestrator:
    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(8)  # 并发模型调用上限

    async def run_ai_turn(self, engine, seat: int, token: int) -> None:
        """AI 座位的一次行动。全程不持有引擎锁（除短暂读取与提交）。"""
        try:
            async with self._sem:
                # —— 锁定：构建请求 ——
                async with engine.lock:
                    st = engine.state
                    p = st.player(seat)
                    if (p is None or st.status != "running"
                            or token != st.turn_token or seat not in st.acting_seats):
                        engine._ai_inflight.discard(seat)
                        return
                    request = engine.build_ai_request(seat)
                    cfg_id = p.model_config_id
                    persona_id = p.persona_id
                    phase = st.phase
                    game_id = st.game_id

                # —— 锁外：读取配置、构建提示词、调用模型 ——
                start = time.monotonic()
                cfg = await self._resolve_config(cfg_id)
                persona = await self._load_persona(persona_id)
                if cfg is None:
                    logger.warning("seat %s: 无可用模型配置，执行兜底", seat)
                    await engine.commit_ai(seat, token, None)
                    return
                api_key = decrypt_secret(cfg.encrypted_api_key)
                system, user = build_prompts(engine, seat, request, persona)

                window_kind = request.get("window_kind") or ""
                stream_field = (
                    "speech" if window_kind in _SPEECH_WINDOWS
                    else "chat_message" if window_kind == "wolf_chat"
                    else None
                )
                stream_id = f"ai:{game_id}:{token}:{seat}"
                raw_stream = ""
                shown_stream = ""

                async def on_delta(delta: str) -> None:
                    nonlocal raw_stream, shown_stream
                    raw_stream += delta
                    if not stream_field:
                        return
                    extracted = _extract_json_string_field(raw_stream, stream_field)
                    if not extracted:
                        return
                    if extracted.startswith(shown_stream):
                        chunk = extracted[len(shown_stream):]
                    else:
                        # 模型偶尔会修正已输出片段，前端以当前累计文本覆盖。
                        chunk = extracted
                    shown_stream = extracted
                    await engine.emit_ai_stream(seat, token, stream_id, chunk, "chunk")

                async def on_retry() -> None:
                    nonlocal raw_stream, shown_stream
                    raw_stream = ""
                    shown_stream = ""
                    if stream_field:
                        await engine.emit_ai_stream(seat, token, stream_id, "", "retry")

                max_tokens = _response_token_budget(window_kind, cfg.max_output_tokens)
                result, error_kind, error_msg, usage = await self._call_with_retry(
                    cfg,
                    api_key,
                    system,
                    user,
                    max_tokens=max_tokens,
                    on_delta=on_delta if stream_field else None,
                    on_retry=on_retry if stream_field else None,
                )

                if stream_field:
                    await engine.emit_ai_stream(
                        seat,
                        token,
                        stream_id,
                        shown_stream if result is not None else "",
                        "complete" if result is not None else "fallback",
                    )

                duration_ms = int((time.monotonic() - start) * 1000)
                await self._log_call(game_id, seat, phase, cfg, result, error_kind, error_msg, duration_ms, usage)

                # —— 重新加锁：校验回合令牌并提交 ——
                await engine.commit_ai(seat, token, result)
        except asyncio.CancelledError:
            engine._ai_inflight.discard(seat)
            raise
        except Exception:
            logger.exception("AI turn error seat=%s", seat)
            try:
                await engine.commit_ai(seat, token, None)
            except Exception:
                pass

    async def _resolve_config(self, cfg_id: int | None) -> ModelConfig | None:
        """只解析座位绑定的配置，不在行动失败时切换备用模型。"""
        if not cfg_id:
            return None
        async with SessionLocal() as db:
            cfg = await db.get(ModelConfig, cfg_id)
            return cfg if cfg and cfg.enabled else None

    async def _load_persona(self, persona_id: int | None) -> AIPersona | None:
        if not persona_id:
            return None
        async with SessionLocal() as db:
            return await db.get(AIPersona, persona_id)

    async def _call_with_retry(self, cfg: ModelConfig, api_key: str, system: str, user: str,
                               max_tokens: int | None = None,
                               on_delta=None,
                               on_retry=None,
                               ) -> tuple[dict | None, str, str, dict]:
        """在同一模型上有限重试；支持文本窗口的流式增量。"""
        last_kind, last_msg = "", ""
        usage: dict = {}
        content: str | None = None
        retry_count = min(max(int(settings.ai_max_retries), 0), 2)
        for attempt in range(retry_count + 1):
            if attempt and on_retry:
                await on_retry()
            try:
                if on_delta:
                    content, usage = await call_model_stream(
                        cfg, api_key, system, user, on_delta, max_tokens=max_tokens)
                else:
                    content, usage = await call_model(
                        cfg, api_key, system, user, max_tokens=max_tokens)
                parsed = parse_ai_json(content)
                if parsed is not None:
                    return parsed, "", "", usage
                # 格式错误：尝试修复（提取JSON块），仍失败则重试一次
                last_kind, last_msg = "invalid_json", "模型输出不是合法JSON"
                continue
            except ModelCallError as e:
                last_kind, last_msg = e.kind, e.message
                content = None
                if attempt < retry_count:
                    await asyncio.sleep(0.5)
        return None, last_kind or "error", last_msg, usage

    async def _log_call(self, game_id: int, seat: int, phase: str, cfg: ModelConfig,
                        result: dict | None, error_kind: str, error_msg: str,
                        duration_ms: int, usage: dict) -> None:
        status = "ok" if result is not None else ("timeout" if error_kind == "timeout" else "fallback")
        async with SessionLocal() as db:
            db.add(ModelCallLog(
                game_id=game_id,
                seat_number=seat,
                phase=phase,
                model_config_id=cfg.id,
                model_name=cfg.model_name,
                status=status,
                duration_ms=duration_ms,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                error_type=error_kind,
            ))
            await db.commit()
