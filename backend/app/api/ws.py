"""WebSocket：/ws/game/current 实时对局。"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import settings
from ..database import SessionLocal
from ..models import SessionToken, User
from ..services.game_manager import manager

logger = logging.getLogger("game.ws")
router = APIRouter(tags=["ws"])


async def _auth_user(ws: WebSocket) -> User | None:
    token = ws.cookies.get(settings.cookie_name)
    if not token:
        return None
    async with SessionLocal() as db:
        from datetime import datetime
        row = await db.get(SessionToken, token)
        if row is None or row.expires_at < datetime.utcnow():
            return None
        return await db.get(User, row.user_id)


@router.websocket("/ws/game/current")
async def ws_game(ws: WebSocket):
    user = await _auth_user(ws)
    if user is None:
        await ws.close(code=4401, reason="未登录")
        return
    engine = manager.engine
    if engine is None or engine.state.status in ("lobby", "ended"):
        await ws.close(code=4404, reason="当前没有进行中的对局")
        return
    seat = None
    for p in engine.state.players:
        if p.user_id == user.id:
            seat = p.seat_number
            break
    conn = await manager.hub.connect(ws, user.id, seat)
    try:
        # 初始同步：完整可见事件 + 视图
        await manager.hub.send_sync(conn, 0)
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await conn.send({"type": "pong"})
            elif msg_type == "sync":
                await manager.hub.send_sync(conn, int(data.get("last_seq") or 0))
            elif msg_type in ("speak", "vote", "use_skill", "wolf_explode", "wolf_chat", "sheriff_action", "pass"):
                request_id = str(data.get("request_id") or "")
                if not request_id:
                    await conn.send({"type": "error", "message": "缺少 request_id"})
                    continue
                result = await engine.process_ws_command(
                    user.id, request_id, msg_type, data.get("payload") or {})
                if result.get("ok"):
                    await conn.send({"type": "ack", "request_id": request_id})
                else:
                    await conn.send({"type": "error", "request_id": request_id,
                                     "message": result.get("error", "操作失败"),
                                     "code": result.get("code")})
            else:
                await conn.send({"type": "error", "message": f"未知消息类型: {msg_type}"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws error")
    finally:
        manager.hub.disconnect(conn)
