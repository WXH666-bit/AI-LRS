"""SQLAlchemy 数据模型。"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | admin
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    protocol: Mapped[str] = mapped_column(String(32))  # openai_compatible | anthropic_messages
    base_url: Mapped[str] = mapped_column(String(512))
    model_name: Mapped[str] = mapped_column(String(128))
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    temperature: Mapped[float] = mapped_column(Float, default=0.9)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AIPersona(Base):
    __tablename__ = "ai_personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    speaking_style: Mapped[str] = mapped_column(Text, default="")
    risk_preference: Mapped[str] = mapped_column(Text, default="")  # 激进/保守/均衡
    reasoning_style: Mapped[str] = mapped_column(Text, default="")
    aggression: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="lobby")  # lobby|running|paused|ended
    phase: Mapped[str] = mapped_column(String(32), default="lobby")
    winner: Mapped[str | None] = mapped_column(String(16), nullable=True)  # good | wolf
    end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("game_id", "seat_number", name="uq_game_player_seat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    seat_number: Mapped[int] = mapped_column(Integer)
    controller_type: Mapped[str] = mapped_column(String(16))  # human|ai|trustee
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    model_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    alive: Mapped[bool] = mapped_column(Boolean, default=True)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class GameEvent(Base):
    __tablename__ = "game_events"
    __table_args__ = (
        UniqueConstraint("game_id", "sequence_number", name="uq_game_event_seq"),
        Index("ix_game_event_game_seq", "game_id", "sequence_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    actor_seat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day: Mapped[int] = mapped_column(Integer, default=0)
    night: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str] = mapped_column(String(32), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    visible_to: Mapped[list | None] = mapped_column(JSON, nullable=True)  # None=公开, [3,5]=仅这些座位
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class GameSnapshot(Base):
    __tablename__ = "game_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)  # 快照对应的最后事件序号
    state: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), unique=True)
    winner: Mapped[str] = mapped_column(String(16))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelCallLog(Base):
    __tablename__ = "model_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seat_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase: Mapped[str] = mapped_column(String(32), default="")
    model_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16))  # ok|error|timeout|fallback
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ClientCommand(Base):
    """客户端命令幂等记录：game_id + request_id 唯一。"""

    __tablename__ = "client_commands"
    __table_args__ = (
        UniqueConstraint("game_id", "request_id", name="uq_client_command"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    request_id: Mapped[str] = mapped_column(String(64))
    seat_number: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
