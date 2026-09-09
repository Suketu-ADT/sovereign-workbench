"""
Alembic migration runner reusing the application's async database connection.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.session import engine


from sqlalchemy import text

# Dedicated fixed 64-bit key for PostgreSQL migration serialization across concurrent workers
MIGRATION_ADVISORY_LOCK_ID = 4242424243


def _get_alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def _upgrade_head(connection) -> None:
    cfg = _get_alembic_config()
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def run_migrations() -> None:
    """
    Run all pending Alembic migrations using the app's async engine connection.
    In multi-worker production (PostgreSQL), acquires a transaction-level advisory lock
    to prevent concurrent worker processes from racing on alembic_version bookkeeping.
    """
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": MIGRATION_ADVISORY_LOCK_ID},
            )
        await conn.run_sync(_upgrade_head)
