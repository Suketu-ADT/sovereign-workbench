"""
Environment-based application settings.
Loaded from .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration drawn from environment variables — never hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────
    # Default: SQLite for local dev. Docker .env overrides to Postgres.
    DATABASE_URL: str = "sqlite+aiosqlite:///./sovereign.db"

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # ── Seed ──────────────────────────────────────────────────
    SEED_PASSWORD: str = "changeme123"

    # ── Prompt Guard (Llama-Guard-3) ──────────────────────────
    PROMPT_GUARD_ENABLED: bool = True
    PROMPT_GUARD_URL: str = "http://127.0.0.1:11434"
    PROMPT_GUARD_MODEL: str = "llama-guard3:1b"
    PROMPT_GUARD_TIMEOUT: float = 3.0

    # ── Qdrant Vector DB & RAG ────────────────────────────────
    QDRANT_STORAGE_PATH: str = "./qdrant_storage"
    QDRANT_URL: str | None = None
    QDRANT_COLLECTION: str = "operational_manuals"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RAG_TOP_K: int = 3

    # ── Multimodal Vision (Qwen2.5-VL / OpenCV) ───────────────
    VISION_MODEL_ENABLED: bool = True
    VISION_MODEL_URL: str = "http://127.0.0.1:11434"
    VISION_MODEL_NAME: str = "qwen2.5-vl:7b"
    VISION_TIMEOUT: float = 5.0


settings = Settings()


