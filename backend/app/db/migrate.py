"""
Alembic migration runner reusing the application's async database connection.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.session import engine


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
    """Run all pending Alembic migrations using the app's async engine connection."""
    async with engine.connect() as conn:
        await conn.run_sync(_upgrade_head)
