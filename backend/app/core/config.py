import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VoiceAI API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-me-in-production-use-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "postgresql+asyncpg://postgres:1234@localhost:5432/voice_ai"

    chroma_path: str = "./chroma_data"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 25

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_max_tokens: int = 512

    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"

    cors_origins: str = "http://localhost:3000"

    rate_limit_default: str = "120/minute"

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_api_key(cls, v: str) -> str:
        key = (v or "").strip()
        if not key:
            raise ValueError(
                "GROQ_API_KEY is required. "
                f"Set it in environment or in {_ENV_FILE}"
            )
        if not key.startswith("gsk_"):
            raise ValueError(
                "GROQ_API_KEY appears invalid (expected gsk_ prefix)"
            )
        return key

    @field_validator("groq_max_tokens")
    @classmethod
    def validate_groq_max_tokens(cls, v: int) -> int:
        if v < 1:
            raise ValueError("GROQ_MAX_TOKENS must be at least 1")
        if v > 8192:
            raise ValueError("GROQ_MAX_TOKENS must not exceed 8192")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")

    @property
    def groq_chat_url(self) -> str:
        return f"{self.groq_base_url.rstrip('/')}/chat/completions"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
