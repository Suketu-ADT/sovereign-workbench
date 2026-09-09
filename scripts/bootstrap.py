"""
Sovereign On-Premise Agentic AI Workbench — Offline Air-Gap Bootstrapper.

Pre-warms all local database migrations, seeds default industrial operators,
pre-caches FastEmbed transformer weights, and verifies offline system readiness.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = ROOT_DIR / "data"

sys.path.insert(0, str(BACKEND_DIR))


def main():
    print("=" * 60)
    print("SOVEREIGN WORKBENCH — AIR-GAPPED OFFLINE BOOTSTRAP INITIALIZER")
    print("=" * 60)

    # 1. Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Local data directory initialized: {DATA_DIR}")

    # 2. Database migrations & seed
    print("[2/4] Running Alembic migrations and database seeding...")
    from app.db.migrate import run_migrations
    from app.db.seed import seed_database
    from app.db.session import async_session_factory

    async def _init_db():
        await run_migrations()
        async with async_session_factory() as db:
            await seed_database(db)

    asyncio.run(_init_db())
    print("      Database tables and initial genesis block ready.")

    # 3. Vector Embeddings Pre-Cache
    print("[3/4] Pre-caching FastEmbed model and indexing plant SOP manuals...")
    from app.services import retrieval_service
    retrieval_service.initialize()
    print("      Vector retrieval model loaded and manuals indexed.")

    # 4. Verification Check
    print("[4/4] Verifying cryptographic ledger integrity...")
    from app.services import audit_service
    async def _verify_audit():
        async with async_session_factory() as db:
            valid, count, broken = await audit_service.verify_chain(db)
            print(f"      Audit chain verified: valid={valid}, entries={count}, broken_at={broken}")
            if not valid:
                raise RuntimeError(f"Audit chain verification failed at entry {broken}")

    asyncio.run(_verify_audit())

    print("=" * 60)
    print("AIR-GAPPED BOOTSTRAP COMPLETE: SYSTEM IS 100% READY FOR OFFLINE DEPLOYMENT")
    print("=" * 60)
    print("To start the backend server:")
    print("  python -m uvicorn app.main:app --port 8000 (from backend/)")
    print("To launch full multi-container stack:")
    print("  docker compose up -d (from root)")


if __name__ == "__main__":
    main()
