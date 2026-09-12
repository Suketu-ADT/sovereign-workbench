"""
Sovereign Workbench — FastAPI Application

Phase 0/1: Authentication, RBAC, rate limiting, and hash-chained
audit trail.
Phase 2-7: Defense-in-depth pipeline (Llama-Guard, Qdrant RBAC RAG,
Qwen2.5-VL vision, sandboxed calculation, LangGraph HITL planner).
Production: Multi-worker resilience, advisory locks, PostgreSQL checkpointing.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import ai, approvals, audit, auth, documents, query
from app.core.config import settings
from app.db.migrate import run_migrations
from app.db.seed import seed_database
from app.db.session import async_session_factory, engine
from app.services import planner_service, retrieval_service
from app.services.prompt_guard import get_llm_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Production security checks (refuse default/insecure JWT_SECRET)
      2. Run serialized database migrations (Postgres advisory lock)
      3. Seed demo operators if needed
      4. Initialize persistent Qdrant collection and operational manuals
      5. Initialize LangGraph Postgres checkpointer
    Shutdown:
      1. Close LangGraph checkpointer pool
      2. Dispose SQLAlchemy engine
    """
    # Fix E: Enforce secure JWT_SECRET in production
    if settings.ENVIRONMENT.lower() in ("production", "prod", "staging"):
        insecure_secrets = (
            "CHANGE_ME_IN_PRODUCTION",
            "sovereign_industrial_airgapped_super_secret_key_change_in_prod_12345",
            "dev-only-secret-change-in-production",
            "",
        )
        if settings.JWT_SECRET in insecure_secrets or len(settings.JWT_SECRET) < 32:
            raise RuntimeError(
                f"FATAL: Insecure or default JWT_SECRET detected in production environment: '{settings.JWT_SECRET}'. "
                "Production deployments must provide a strong, non-default JWT_SECRET of at least 32 characters."
            )
        logger.info("Production JWT_SECRET strength validation passed.")

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

    # Initialize LangGraph checkpointer (AsyncPostgresSaver on Postgres)
    logger.info("Initializing LangGraph checkpointer...")
    await planner_service.init_checkpointer()
    logger.info("Planner service checkpointer ready.")

    yield

    await planner_service.close_checkpointer()
    await engine.dispose()
    logger.info("Database engine and checkpointer pool disposed.")


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
app.include_router(documents.router)
app.include_router(audit.router)
app.include_router(approvals.router)
app.include_router(ai.router)


# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health(response: Response):
    """
    System health check.
    Verifies database connectivity and returns subsystem operational statuses.
    """
    db_status = "healthy"
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Health check database ping failed: %s", e)
        db_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    llm_status = get_llm_status()

    return {
        "status": "ok" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "prompt_guard_llm_status": llm_status,
    }


# ── Static Frontend UI (Local Dev & Production) ───────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if (ROOT_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(ROOT_DIR), html=True), name="static_root")

