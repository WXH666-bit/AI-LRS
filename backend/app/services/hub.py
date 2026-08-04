"""WebSocket 连接管理与事件分发（按可见性过滤）。"""
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("game.hub")


class Connection:
    def __init__(self, ws: WebSocket, user_id: int, seat: int | None):
        self.ws = ws
        self.user_id = user_id
        self.seat = seat
        self.send_lock = asyncio.Lock()

    async def send(self, data: dict) -> None:
        """发送 JSON；死连接（TCP半开）用超时保护，避免广播永久阻塞引擎。"""
        async with self.send_lock:
            try:
                await asyncio.wait_for(self.ws.send_json(data), timeout=10)
            except asyncio.TimeoutError:
                raise ConnectionError("send timeout")
            except Exception:
                raise


class Hub:
    def __init__(self) -> None:
        self.conns: set[Connection] = set()
        self.engine: object | None = None  # GameEngine，由管理器注入

    def is_user_online(self, user_id: int) -> bool:
        return any(c.user_id == user_id for c in self.conns)

    async def connect(self, ws: WebSocket, user_id: int, seat: int | None) -> Connection:
        await ws.accept()
        conn = Connection(ws, user_id, seat)
        self.conns.add(conn)
        return conn

    def disconnect(self, conn: Connection) -> None:
        self.conns.discard(conn)

    def _public_event(self, ev: dict) -> dict:
        return {k: ev[k] for k in ("seq", "type", "actor_seat", "day", "night", "phase", "payload")}

    async def broadcast_event(self, ev: dict) -> None:
        vis = ev.get("visible_to")
        data = self._public_event(ev)
        for conn in list(self.conns):
            if vis is None or conn.seat in vis:
                try:
                    await conn.send({"type": "event", "event": data})
                except Exception:
                    logger.info("drop dead connection user=%s", conn.user_id)
                    self.conns.discard(conn)

    async def broadcast_view(self) -> None:
        engine = self.engine
        if engine is None:
            return
        for conn in list(self.conns):
            try:
                view = engine.build_view(conn.seat)
                await conn.send({"type": "view", "view": view})
            except Exception:
                logger.info("drop dead connection user=%s", conn.user_id)
                self.conns.discard(conn)

    async def send_sync(self, conn: Connection, last_seq: int) -> None:
        engine = self.engine
        if engine is None:
            return
        missing = []
        for ev in engine.events:
            if ev["seq"] <= last_seq:
                continue
            vis = ev.get("visible_to")
            if vis is not None and conn.seat not in vis:
                continue
            missing.append(self._public_event(ev))
        await conn.send({"type": "sync_events", "events": missing})
        view = engine.build_view(conn.seat)
        await conn.send({"type": "view", "view": view})
