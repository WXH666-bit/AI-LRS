"""测试环境：使用独立临时数据库。必须在导入 app 模块之前设置环境变量。"""
import os
import tempfile

_TMPDIR = tempfile.mkdtemp(prefix="ww_test_")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(_TMPDIR, "test.db").replace("\\", "/")
os.environ["APP_SECRET_KEY"] = "test-secret-key-0000"
os.environ["HUMAN_ACTION_TIMEOUT"] = "45"

import asyncio  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.database import Base, engine as db_engine  # noqa: E402
from app.services.game_manager import manager  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fresh_db():
    """每个测试前重建数据库，并重置全局管理器。"""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    if manager.engine is not None:
        await manager.engine.stop_loop()
    manager.engine = None
    manager.hub.conns.clear()
    manager.hub.engine = None
    yield
    if manager.engine is not None:
        await manager.engine.stop_loop()
    manager.engine = None
