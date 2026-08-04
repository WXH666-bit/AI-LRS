"""SQLAlchemy 异步引擎与 SQLite 初始化。"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


async def init_db() -> None:
    """建表 + 种子管理员。"""
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_admin()


async def seed_admin() -> None:
    from sqlalchemy import select

    from . import models
    from .config import settings
    from .security import hash_password

    async with SessionLocal() as db:
        exists = await db.scalar(select(models.User).limit(1))
        if exists is not None:
            return
        password = settings.admin_password or "admin123"
        user = models.User(
            username=settings.admin_username,
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(user)
        await db.commit()
