"""认证依赖：HttpOnly Cookie 会话。"""
from datetime import datetime

from fastapi import HTTPException, Request
from fastapi.responses import Response

from ..config import settings
from ..database import SessionLocal
from ..models import SessionToken, User
from ..security import new_session_token


async def get_current_user(request: Request) -> User | None:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    async with SessionLocal() as db:
        row = await db.get(SessionToken, token)
        if row is None or row.expires_at < datetime.utcnow():
            return None
        return await db.get(User, row.user_id)


async def require_user(request: Request) -> User:
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


async def require_admin(request: Request) -> User:
    user = await require_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def create_session(db, user_id: int) -> tuple[str, datetime]:
    from datetime import datetime, timedelta

    from ..config import settings
    from ..models import SessionToken
    from ..security import new_session_token

    token = new_session_token()
    expires = datetime.utcnow() + timedelta(seconds=settings.session_ttl_seconds)
    db.add(SessionToken(token=token, user_id=user_id, expires_at=expires))
    await db.commit()
    return token, expires


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")
