"""
Query route — the defense pipeline entry point.

Pipeline steps (in order):
  1. Rate limit check
  2. RBAC check
  3. If both pass → stub response (retrieval/vision/calculation
     are Phases 3-5)

Each step writes an audit_log entry via the centralized audit service.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.query import QueryRequest, QueryResponse
from app.services import (
    audit_service,
    prompt_guard,
    rate_limiter,
    rbac_service,
    retrieval_service,
)


router = APIRouter(tags=["Query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Submit a query through the defense pipeline",
)
async def submit_query(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    clearance = current_user["clearance_level"]

    # ── Step 1: Rate limit check ──────────────────────────────
    allowed, retry_after = rate_limiter.check_rate_limit(user_id)

    if not allowed:
        async with audit_service.audit_transaction():
            await audit_service.append_entry(
                db=db,
                event_type="RATE_LIMIT_BLOCK",
                detail=f"Rate limit exceeded for user {current_user['email']}",
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_s": retry_after,
            },
        )

    # ── Step 2: Prompt safety check (PromptGuard) ─────────────
    safe, reason = await prompt_guard.is_safe(body.text)

    if not safe:
        async with audit_service.audit_transaction():
            await audit_service.append_entry(
                db=db,
                event_type="PROMPT_SAFETY_BLOCK",
                detail=f"Prompt rejected by PromptGuard: {reason}",
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Prompt blocked by safety screening",
                "reason": reason,
            },
        )

    # ── Step 3: RBAC check ────────────────────────────────────
    rbac_allowed, required_level = rbac_service.check_access(body.text, clearance)

    if not rbac_allowed:
        async with audit_service.audit_transaction():
            await audit_service.append_entry(
                db=db,
                event_type="RBAC_BLOCK",
                detail=(
                    f"Insufficient clearance: required level {required_level}, "
                    f"user {current_user['email']} has level {clearance}"
                ),
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Insufficient clearance",
                "required_level": required_level,
                "current_level": clearance,
            },
        )

    # ── Step 4: Document Retrieval & Query Acceptance ────────
    retrieved_chunks = retrieval_service.retrieve(
        query=body.text,
        operator_clearance=clearance,
    )

    async with audit_service.audit_transaction():
        await audit_service.append_entry(
            db=db,
            event_type="QUERY_SUBMITTED",
            detail=f"Query accepted: {body.text[:200]}",
            actor_user_id=user_id,
        )

        # Audit retrieval chunks accessed with security clearance ratings
        if retrieved_chunks:
            chunk_summary = ", ".join(
                f"[{c.sop_id} {c.unit} L{c.min_clearance}]"
                for c in retrieved_chunks
            )
            audit_detail = (
                f"Retrieved {len(retrieved_chunks)} chunks for clearance {clearance}: "
                f"{chunk_summary}"
            )
        else:
            audit_detail = f"Zero document chunks accessible for clearance {clearance}"

        await audit_service.append_entry(
            db=db,
            event_type="RETRIEVAL_EXECUTED",
            detail=audit_detail,
            actor_user_id=user_id,
        )


        # Query complete (vision/calculation are Phases 4-5)
        await audit_service.append_entry(
            db=db,
            event_type="QUERY_COMPLETE",
            detail=(
                f"Query processed with {len(retrieved_chunks)} retrieved chunks — "
                "vision/calculation to be integrated in Phases 4-5"
            ),
            actor_user_id=user_id,
        )

        await db.commit()

    return QueryResponse(
        status="accepted_stub",
        note=(
            f"Retrieved {len(retrieved_chunks)} role-filtered manual chunks — "
            "vision/calculation to be integrated in Phases 4-5"
        ),
        retrieved_chunks=retrieved_chunks,
    )

