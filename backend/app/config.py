"""应用配置。所有路径基于项目根目录（AI_LRS），与启动目录无关。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI狼人杀"
    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'werewolf.db').as_posix()}"

    # 应用主加密密钥（Fernet 派生），用于加密模型 API Key
    secret_key: str = "dev-only-secret-change-me"

    cookie_name: str = "ww_session"
    session_ttl_seconds: int = 7 * 24 * 3600

    admin_username: str = "admin"
    admin_password: str = ""  # 为空时使用 admin/admin123

    # 真人行动限时
    human_action_timeout: int = 45
    wolf_window_timeout: int = 60   # 狼人夜间窗口
    apply_window_timeout: int = 60  # 上警窗口

    # AI 调用
    ai_timeout_seconds: int = 30
    ai_max_retries: int = 1

    # 前端地址（CORS）
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
