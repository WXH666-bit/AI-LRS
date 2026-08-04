"""账号：注册、登录、退出、当前用户。"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from ..database import SessionLocal
from ..models import SessionToken, User
from ..schemas import LoginIn, RegisterIn
from ..security import hash_password, verify_password
from .deps import clear_session_cookie, create_session, get_current_user, set_session_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


def user_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role,
            "games_played": u.games_played, "wins": u.wins}


@router.post("/register")
async def register(body: RegisterIn):
    async with SessionLocal() as db:
        exists = await db.scalar(select(User).where(User.username == body.username))
        if exists:
            raise HTTPException(status_code=409, detail="用户名已存在")
        user = User(username=body.username, password_hash=hash_password(body.password), role="user")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return {"ok": True, "user": user_dict(user)}


@router.post("/login")
async def login(body: LoginIn, response: Response):
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == body.username))
        if user is None or not verify_password(user.password_hash, body.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token, _ = await create_session(db, user.id)
    set_session_cookie(response, token)
    return {"ok": True, "user": user_dict(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("ww_session")
    if token:
        async with SessionLocal() as db:
            row = await db.get(SessionToken, token)
            if row:
                await db.delete(row)
                await db.commit()
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    if user is None:
        return {"user": None}
    return {"user": user_dict(user)}
