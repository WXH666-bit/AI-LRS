"""单活动对局管理器：当前对局的创建、查询、观战控制。"""
import logging

from sqlalchemy import select

from ..ai.orchestrator import AIOrchestrator
from ..database import SessionLocal
from ..game.engine import GameEngine, GameError
from ..game.state import GameState, PlayerState
from ..models import Game
from .hub import Hub

logger = logging.getLogger("game.manager")


class GameManager:
    def __init__(self) -> None:
        self.engine: GameEngine | None = None
        self.hub = Hub()
        self.ai = AIOrchestrator()

    async def init(self) -> None:
        """启动时恢复未结束对局。"""
        engine = await GameEngine.recover(hub=self.hub)
        if engine is not None:
            engine._ai = self.ai
            self.engine = engine
            self.hub.engine = engine
            logger.info("recovered game %s status=%s phase=%s", engine.state.game_id,
                        engine.state.status, engine.state.phase)

    async def shutdown(self) -> None:
        if self.engine:
            await self.engine.stop_loop()

    async def create_game(self, user, board_size: int) -> GameEngine:
        if self.engine is not None and self.engine.state.status != "ended":
            raise GameError("已有未结束的对局，无法创建新对局", code="game_exists")
        # 数据库层面兜底：不允许同时存在第二场未结束对局
        async with SessionLocal() as db:
            exists = (await db.execute(
                select(Game).where(Game.status.in_(("lobby", "running", "paused")))
                .limit(1))).scalars().first()
            if exists is not None:
                raise GameError("已有未结束的对局，无法创建新对局", code="game_exists")
            row = Game(board_size=board_size, status="lobby", phase="lobby", created_by=user.id)
            db.add(row)
            await db.commit()
            await db.refresh(row)
            game_id = row.id

        st = GameState(game_id=game_id, board_size=board_size)
        for seat in range(1, board_size + 1):
            st.players.append(PlayerState(seat_number=seat, controller_type="empty"))
        engine = GameEngine(state=st, hub=self.hub)
        engine._ai = self.ai
        self.engine = engine
        self.hub.engine = engine
        engine._snapshot_required = True
        await engine._persist_lobby()
        return engine

    # ---------------- 查询 ----------------
    async def current_game(self) -> Game | None:
        async with SessionLocal() as db:
            return (await db.execute(
                select(Game).order_by(Game.id.desc()).limit(1))).scalars().first()

    async def history(self, limit: int = 50) -> list[Game]:
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(Game).where(Game.status == "ended")
                .order_by(Game.id.desc()).limit(limit))).scalars().all()
            return list(rows)

    # ---------------- 观战控制 ----------------
    async def pause(self, user) -> None:
        engine = self._running_engine()
        self._check_host(engine, user)
        self._check_all_ai(engine)
        await engine.pause()

    async def resume(self, user) -> None:
        engine = self._running_engine()
        self._check_host(engine, user)
        self._check_all_ai(engine)
        await engine.resume()

    async def speed(self, user, speed: int) -> None:
        engine = self._running_engine()
        self._check_host(engine, user)
        self._check_all_ai(engine)
        await engine.set_speed(speed)

    def _running_engine(self) -> GameEngine:
        if self.engine is None or self.engine.state.status not in ("running", "paused"):
            raise GameError("当前没有进行中的对局")
        return self.engine

    async def _check_host(self, engine: GameEngine, user) -> None:
        async with SessionLocal() as db:
            row = await db.get(Game, engine.state.game_id)
            if row is None or row.created_by != user.id:
                raise GameError("只有房主可以执行此操作")

    @staticmethod
    def _check_all_ai(engine: GameEngine) -> None:
        if not engine.state.all_ai():
            raise GameError("仅全AI对局支持暂停与调速")


manager = GameManager()
