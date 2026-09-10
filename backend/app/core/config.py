"""
Environment-based application settings.
Loaded from .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration drawn from environment variables — never hardcoded."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────
    ENVIRONMENT: str = "development"

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

    # ── Remote API / OpenRouter / OpenAI-Compatible Gateway ──
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"

    # ── Multimodal Vision (Qwen2.5-VL 72B / OpenCV) ───────────
    VISION_MODEL_ENABLED: bool = True
    VISION_MODEL_URL: str = "http://127.0.0.1:11434"
    VISION_MODEL_NAME: str = "qwen/qwen-2.5-vl-72b-instruct"
    VISION_TIMEOUT: float = 30.0

    # ── LangGraph Planner & Reasoning (Qwen2.5-32B) ───────────
    PLANNER_MODEL_ENABLED: bool = True
    PLANNER_MODEL_URL: str = "http://127.0.0.1:11434"
    PLANNER_MODEL_NAME: str = "qwen/qwen2.5-32b-instruct"
    PLANNER_TIMEOUT: float = 30.0

    # ── Multi-Model Routing & Sovereign Mode ───────────────────
    HF_TOKEN: str | None = None
    HF_BASE_URL: str = "https://router.huggingface.co/v1"
    SOVEREIGN_MODE: bool = False
    LOCAL_MODEL_BASE_URL: str = "http://localhost:8000/v1"


settings = Settings()



