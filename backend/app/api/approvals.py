"""
Human-in-the-Loop (HITL) approval endpoints.
Allows authorized operators to inspect pending sensitive actuator commands
and resume interrupted LangGraph workflows with cryptographic audit commitment.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.query import HITLDecisionRequest, HITLDecisionResponse
from app.services import audit_service, planner_service

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get(
    "/pending",
    summary="List all workflows awaiting Human-in-the-Loop authorization",
)
async def list_pending_approvals(
    current_user: dict = Depends(get_current_user),
):
    """Lists all active approval gates paused in LangGraph."""
    pending = planner_service.list_pending_approvals()
    items = [
        {
            "thread_id": p["thread_id"],
            "unit": p["unit"],
            "operator_email": p["operator_email"],
            "approval_details": p["approval_details"],
        }
        for p in pending
    ]
    return {
        "count": len(pending),
        "approvals": items,
        "pending_approvals": items,
    }


@router.post(
    "/{thread_id}/decision",
    response_model=HITLDecisionResponse,
    summary="Authorize or reject a sensitive actuator command",
)
async def submit_approval_decision(
    thread_id: str,
    body: HITLDecisionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits operator decision (approve/reject) to resume paused LangGraph state
    and commits cryptographic audit record to the SHA-256 chain.
    """
    decision_lower = body.decision.strip().lower()
    if decision_lower not in ("approve", "approved", "reject", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'approve' or 'reject'",
        )

    approved = decision_lower in ("approve", "approved")
    operator_email = current_user.get("email", "operator")
    operator_role = current_user.get("role", "Operator")
    operator_name = current_user.get("name") or operator_email

    try:
        resume_res = planner_service.resume_plan(
            thread_id=thread_id,
            approved=approved,
            operator_email=operator_email,
            comment=body.comment,
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Commit decision to cryptographic audit log
    event_type = "HITL_APPROVAL" if approved else "HITL_REJECTION"
    action = resume_res["action"]
    target = resume_res["target"]

    detail_str = (
        f"{action} {'approved' if approved else 'rejected'} by {operator_role} "
        f"({operator_name}) on target {target}"
        + (f" — Comment: {body.comment}" if body.comment else "")
    )

    import uuid
    user_id = uuid.UUID(current_user["sub"]) if "sub" in current_user else None

    async with audit_service.audit_transaction():
        entry = await audit_service.append_entry(
            db=db,
            event_type=event_type,
            detail=detail_str,
            actor_user_id=user_id,
        )
        await db.commit()

    return HITLDecisionResponse(
        thread_id=thread_id,
        status=resume_res["status"],
        action=action,
        target=target,
        operator_email=operator_email,
        audit_hash=entry.hash if entry else None,
        note=resume_res.get("synthesis", "Decision recorded."),
    )
