"""对局 REST API。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..database import SessionLocal
from ..game.constants import role_setup_for
from ..game.engine import GameError
from ..models import Game, GameEvent, GamePlayer, User
from ..schemas import AIFillIn, AISeatIn, CreateGameIn, JoinIn, ReadyIn, SpeedIn
from .deps import require_admin, require_user
from ..services.game_manager import manager

router = APIRouter(tags=["game"])


def _game_meta(row: Game, user_id: int | None) -> dict:
    return {
        "id": row.id,
        "board_size": row.board_size,
        "status": row.status,
        "phase": row.phase,
        "winner": row.winner,
        "end_reason": row.end_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "is_host": row.created_by == user_id,
    }


async def _game_summary(user: User | None):
    row = await manager.current_game()
    if row is None:
        return {"game": None, "players": [], "me": None}
    engine = manager.engine
    user_id = user.id if user else None
    meta = _game_meta(row, user_id)
    players, me = [], None
    if engine is not None and engine.state.game_id == row.id:
        st = engine.state
        for p in st.players:
            if p.controller_type == "empty":
                continue
            players.append({
                "seat": p.seat_number,
                "name": st.display_name(p.seat_number),
                "controller_type": p.controller_type,
                "user_id": p.user_id,
                "alive": p.alive,
                "ready": p.ready,
                "is_host": p.is_host,
                "role": p.role if st.roles_revealed else None,
                "persona_name": p.persona_name,
                "model_config_id": p.model_config_id,
            })
        if user_id is not None:
            for p in st.players:
                if p.user_id == user_id and p.controller_type == "human":
                    me = {"seat": p.seat_number, "controller_type": p.controller_type,
                          "ready": p.ready, "is_host": p.is_host, "role": p.role}
    else:
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(GamePlayer).where(GamePlayer.game_id == row.id)
                .order_by(GamePlayer.seat_number))).scalars().all()
            for p in rows:
                players.append({
                    "seat": p.seat_number,
                    "name": p.snapshot.get("user_name") or p.snapshot.get("persona_name") or f"{p.seat_number}号",
                    "controller_type": p.controller_type,
                    "user_id": p.user_id,
                    "alive": p.alive,
                    "ready": p.ready,
                    "is_host": p.is_host,
                    "role": p.role if row.status == "ended" else None,
                    "persona_name": p.snapshot.get("persona_name"),
                })
            if user_id is not None:
                for p in rows:
                    if p.user_id == user_id and p.controller_type == "human":
                        me = {"seat": p.seat_number, "controller_type": p.controller_type,
                              "ready": p.ready, "is_host": p.is_host, "role": p.role}
    return {"game": meta, "players": players, "me": me}


@router.get("/game/current")
async def get_current(request: Request):
    from .deps import get_current_user
    user = await get_current_user(request)
    return await _game_summary(user)


@router.post("/game/current")
async def create_game(body: CreateGameIn, user: User = Depends(require_user)):
    try:
        engine = await manager.create_game(user, body.board_size)
    except GameError as e:
        raise HTTPException(status_code=409, detail=e.message)
    return {"ok": True, "game_id": engine.state.game_id}


@router.post("/game/current/join")
async def join(body: JoinIn, user: User = Depends(require_user)):
    if manager.engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    try:
        async with manager.engine.lock:
            result = await manager.engine.join(user.id, user.username, body.seat_number)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True, **result}


@router.post("/game/current/leave")
async def leave(user: User = Depends(require_user)):
    if manager.engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    async with manager.engine.lock:
        await manager.engine.leave(user.id)
    return {"ok": True}


@router.post("/game/current/ready")
async def ready(body: ReadyIn, user: User = Depends(require_user)):
    if manager.engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    try:
        async with manager.engine.lock:
            await manager.engine.set_ready(user.id, body.ready)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/ai-seats")
async def ai_seats(body: AISeatIn, user: User = Depends(require_user)):
    engine = manager.engine
    if engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    try:
        await manager._check_host(engine, user)
        async with engine.lock:
            await engine.ai_seat(body.seat_number, body.action, body.model_config_id, body.persona_id)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/ai-fill")
async def ai_fill(body: AIFillIn, user: User = Depends(require_user)):
    engine = manager.engine
    if engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    try:
        await manager._check_host(engine, user)
        async with engine.lock:
            await engine.ai_fill(body.model_config_id, body.persona_id)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/start")
async def start_game(user: User = Depends(require_user)):
    engine = manager.engine
    if engine is None:
        raise HTTPException(status_code=404, detail="当前没有对局")
    try:
        await manager._check_host(engine, user)
        async with engine.lock:
            await engine.start_game()
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/force-end")
async def force_end(user: User = Depends(require_admin)):
    """管理员强制结束当前对局。"""
    try:
        await manager.force_end("管理员强制结束")
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/pause")
async def pause(user: User = Depends(require_user)):
    try:
        await manager.pause(user)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/resume")
async def resume(user: User = Depends(require_user)):
    try:
        await manager.resume(user)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


@router.post("/game/current/speed")
async def speed(body: SpeedIn, user: User = Depends(require_user)):
    try:
        await manager.speed(user, body.speed)
    except GameError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True}


# ---------------- 历史与回放 ----------------
@router.get("/games/history")
async def history(user: User = Depends(require_user)):
    rows = await manager.history(limit=50)
    return {"games": [_game_meta(r, user.id) for r in rows]}


@router.get("/games/{game_id}")
async def game_detail(game_id: int, user: User = Depends(require_user)):
    async with SessionLocal() as db:
        row = await db.get(Game, game_id)
        if row is None:
            raise HTTPException(status_code=404, detail="对局不存在")
        players = (await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game_id)
            .order_by(GamePlayer.seat_number))).scalars().all()
        meta = _game_meta(row, user.id)
        result = {
            "game": meta,
            "players": [{
                "seat": p.seat_number,
                "name": p.snapshot.get("user_name") or p.snapshot.get("persona_name") or f"{p.seat_number}号",
                "controller_type": p.controller_type,
                "role": p.role,
                "alive": p.alive,
                "is_host": p.is_host,
                "persona_name": p.snapshot.get("persona_name"),
            } for p in players],
        }
        return result


@router.get("/games/{game_id}/replay")
async def replay(game_id: int, user: User = Depends(require_user)):
    async with SessionLocal() as db:
        row = await db.get(Game, game_id)
        if row is None:
            raise HTTPException(status_code=404, detail="对局不存在")
        events = (await db.execute(
            select(GameEvent).where(GameEvent.game_id == game_id)
            .order_by(GameEvent.sequence_number))).scalars().all()
        players = (await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game_id)
            .order_by(GamePlayer.seat_number))).scalars().all()
    return {
        "game": _game_meta(row, user.id),
        "role_setup": role_setup_for(row.board_size),
        "roles": {p.seat_number: p.role for p in players if p.role},
        "events": [{
            "seq": e.sequence_number,
            "type": e.type,
            "actor_seat": e.actor_seat,
            "day": e.day,
            "night": e.night,
            "phase": e.phase,
            "payload": e.payload,
            "visible_to": e.visible_to,
        } for e in events],
    }
