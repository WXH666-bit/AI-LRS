"""AI 编排器：锁定构建请求 → 释放锁调用模型 → 重新加锁校验回合令牌 → 提交。

模型调用期间不持有游戏状态锁；过期结果（阶段已变）直接丢弃。
"""
import asyncio
import logging
import time

from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import AIPersona, ModelCallLog, ModelConfig
from ..security import decrypt_secret
from .adapters import ModelCallError, call_model, parse_ai_json
from .prompts import build_prompts

logger = logging.getLogger("game.ai")

_SPEECH_WINDOWS = frozenset({
    "speech", "election_speak", "election_pk_speak", "lynch_pk_speak", "last_words",
})


def _response_token_budget(window_kind: str | None, configured: int) -> int:
    """限制单回合输出，避免长回复超时或在 JSON 中途被截断。"""
    ceiling = 512 if window_kind in _SPEECH_WINDOWS else 256
    return max(64, min(configured or ceiling, ceiling))


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

                max_tokens = _response_token_budget(request.get("window_kind"), cfg.max_output_tokens)
                result, error_kind, error_msg, usage = await self._call_with_retry(
                    cfg, api_key, system, user, max_tokens=max_tokens)

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
        async with SessionLocal() as db:
            cfg = None
            if cfg_id:
                cfg = await db.get(ModelConfig, cfg_id)
            if cfg is None or not cfg.enabled:
                cfg = (await db.execute(
                    select(ModelConfig).where(ModelConfig.enabled.is_(True))
                    .order_by(ModelConfig.is_default_fallback.desc(), ModelConfig.id))).scalars().first()
            return cfg

    async def _load_persona(self, persona_id: int | None) -> AIPersona | None:
        if not persona_id:
            return None
        async with SessionLocal() as db:
            return await db.get(AIPersona, persona_id)

    async def _call_with_retry(self, cfg: ModelConfig, api_key: str, system: str, user: str,
                               max_tokens: int | None = None
                               ) -> tuple[dict | None, str, str, dict]:
        """最多重试一次；JSON 解析失败时修复一次。返回 (解析结果, error_kind, error_msg, usage)。"""
        last_kind, last_msg = "", ""
        usage: dict = {}
        content: str | None = None
        for attempt in range(settings.ai_max_retries + 1):
            try:
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
