"""
Pytest configuration and test database isolation fixture.

Ensures every test run uses a fresh, isolated temporary SQLite database
and never mutates or depends on the dev database (sovereign.db).
"""

import asyncio
import os
import tempfile
import pytest

# 1. Generate temp DB file and set DATABASE_URL BEFORE any app modules are imported
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
# Remove the empty file so SQLite can initialize it cleanly
if os.path.exists(_db_path):
    os.remove(_db_path)

_normalized_path = _db_path.replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_normalized_path}"
os.environ["QDRANT_STORAGE_PATH"] = ":memory:"

# 2. Now import app db modules with the test DATABASE_URL active
from app.db.seed import seed_database
from app.db.session import Base, async_session_factory, engine
from app.services import retrieval_service


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Session-scoped autouse fixture that initializes tables, seeds demo data,
    and initializes in-memory vector retrieval for the test session.
    """
    async def _init_db():
        from app.db.migrate import run_migrations
        await run_migrations()
        async with async_session_factory() as db:
            await seed_database(db)

    asyncio.run(_init_db())
    retrieval_service.initialize()


    yield

    async def _teardown():
        await engine.dispose()

    asyncio.run(_teardown())

    if os.path.exists(_db_path):
        try:
            os.remove(_db_path)
        except OSError:
            pass
