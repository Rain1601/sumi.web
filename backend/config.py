from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root (parent of backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_debug: bool = True
    cors_origins: str = "http://localhost:3000"

    # LiveKit
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sumi.db"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # AIHubMix unified API gateway (LLM + TTS)
    aihubmix_api_key: str = ""
    aihubmix_base_url: str = "https://aihubmix.com/v1"

    # 阿里云百炼 DashScope (Paraformer ASR + CosyVoice TTS)
    dashscope_api_key: str = ""
    dashscope_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

    # App base URL (for DashScope file ASR — needs externally accessible URL)
    app_base_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def db_path(self) -> Path:
        """Extract SQLite file path for directory creation."""
        if "sqlite" in self.database_url:
            path_part = self.database_url.split("///")[-1]
            return Path(path_part).parent
        return Path(".")


settings = Settings()
