"""
Audit log routes — read, verify, and export the hash-chained ledger.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.audit import (
    AuditEntryResponse,
    AuditExportResponse,
    AuditListResponse,
    AuditVerifyResponse,
)
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get(
    "",
    response_model=AuditListResponse,
    summary="List audit log entries (newest first)",
)
async def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entries, next_cursor = await audit_service.get_entries(db, limit, cursor)

    return AuditListResponse(
        entries=[
            AuditEntryResponse.model_validate(e) for e in entries
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/verify",
    response_model=AuditVerifyResponse,
    summary="Verify the integrity of the audit hash chain",
)
async def verify_audit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid, checked, broken_at = await audit_service.verify_chain(db)

    return AuditVerifyResponse(
        valid=valid,
        entries_checked=checked,
        broken_at_index=broken_at,
    )


@router.get(
    "/export",
    response_model=AuditExportResponse,
    summary="Export the full audit ledger",
)
async def export_audit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    operator_info = {
        "id": current_user["sub"],
        "email": current_user["email"],
        "role": current_user["role"],
        "clearance_level": current_user["clearance_level"],
    }

    result = await audit_service.export_ledger(db, operator=operator_info)

    # Convert ledger entries to response models
    result["ledger"] = [
        AuditEntryResponse.model_validate(e) for e in result["ledger"]
    ]

    return AuditExportResponse(**result)
