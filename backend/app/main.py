"""
Sovereign Workbench — FastAPI Application

Phase 0/1: Authentication, RBAC, rate limiting, and hash-chained
audit trail. Pipeline stubs for retrieval/vision/calculation.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import approvals, audit, auth, query
from app.db.migrate import run_migrations
from app.db.seed import seed_database
from app.db.session import async_session_factory, engine
from app.services import retrieval_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run migrations, seed demo data, initialize vector DB. Shutdown: dispose engine."""
    logger.info("Running database migrations...")
    await run_migrations()
    logger.info("Migrations complete.")

    # Seed demo operators if needed
    async with async_session_factory() as db:
        await seed_database(db)

    # Initialize Qdrant and operational plant manuals
    logger.info("Initializing vector retrieval service and operational manuals...")
    retrieval_service.initialize()
    logger.info("Vector retrieval service ready.")

    yield

    await engine.dispose()
    logger.info("Database engine disposed.")


app = FastAPI(
    title="Sovereign Workbench API",
    description=(
        "Sovereign On-Premise Agentic AI Workbench backend. "
        "Provides authentication, RBAC, rate limiting, PromptGuard input screening, "
        "RBAC-filtered Qdrant vector retrieval, and a SHA-256 hash-chained audit trail."
    ),
    version="0.3.0",
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


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Injects defense-in-depth HTTP security headers into all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ── Mount routers ─────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(audit.router)
app.include_router(approvals.router)



# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """Basic health check endpoint."""
    return {"status": "ok"}
