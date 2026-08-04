"""REST 请求体 Pydantic 模式。"""
from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        if not all(c.isalnum() or c in "_" for c in v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class LoginIn(BaseModel):
    username: str
    password: str


class CreateGameIn(BaseModel):
    board_size: int = Field(ge=6, le=12)

    @field_validator("board_size")
    @classmethod
    def _board(cls, v: int) -> int:
        if v not in (6, 9, 12):
            raise ValueError("板子只支持 6 / 9 / 12 人")
        return v


class JoinIn(BaseModel):
    seat_number: int | None = None


class ReadyIn(BaseModel):
    ready: bool


class AISeatIn(BaseModel):
    seat_number: int
    action: str  # add | remove
    model_config_id: int | None = None
    persona_id: int | None = None


class AIFillIn(BaseModel):
    model_config_id: int | None = None
    persona_id: int | None = None


class SpeedIn(BaseModel):
    speed: int  # 1 | 2 | 3(fast)


class ModelConfigIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    protocol: str  # openai_compatible | anthropic_messages
    base_url: str = Field(min_length=1, max_length=512)
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str = ""
    temperature: float = Field(default=0.9, ge=0, le=2)
    max_output_tokens: int = Field(default=2048, ge=1, le=16384)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    enabled: bool = True
    is_default_fallback: bool = False

    @field_validator("protocol")
    @classmethod
    def _protocol(cls, v: str) -> str:
        if v not in ("openai_compatible", "anthropic_messages"):
            raise ValueError("protocol 必须是 openai_compatible 或 anthropic_messages")
        return v


class PersonaIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    speaking_style: str = ""
    risk_preference: str = ""
    reasoning_style: str = ""
    aggression: int = Field(default=3, ge=1, le=5)
    description: str = ""
