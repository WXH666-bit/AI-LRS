"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .services.game_manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await manager.init()
    logger.info("AI狼人杀后端已启动")
    yield
    await manager.shutdown()
    from .database import engine as db_engine
    await db_engine.dispose()


app = FastAPI(title="AI狼人杀", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api import admin, auth, game, ws  # noqa: E402

app.include_router(auth.router)
app.include_router(game.router)
app.include_router(admin.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"ok": True, "app": settings.app_name}
