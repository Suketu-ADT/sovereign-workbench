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


settings = Settings()
