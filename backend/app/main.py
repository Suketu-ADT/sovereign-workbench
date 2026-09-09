"""
Sovereign Workbench — FastAPI Application

Phase 0/1: Authentication, RBAC, rate limiting, and hash-chained
audit trail. Pipeline stubs for retrieval/vision/calculation.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, auth, query
from app.db.seed import seed_database
from app.db.session import Base, async_session_factory, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed demo data. Shutdown: dispose engine."""
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables ready.")

    # Seed demo operators if needed
    async with async_session_factory() as db:
        await seed_database(db)

    yield

    await engine.dispose()
    logger.info("Database engine disposed.")


app = FastAPI(
    title="Sovereign Workbench API",
    description=(
        "Phase 0/1 backend for the Sovereign On-Premise Agentic AI "
        "Workbench. Provides authentication, RBAC, rate limiting, and "
        "a hash-chained audit trail. Pipeline stubs for Phases 2-5."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (permissive for dev — lock down in production) ───────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ─────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(audit.router)


# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """Basic health check endpoint."""
    return {"status": "ok"}
