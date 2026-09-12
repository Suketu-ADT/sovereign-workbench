"""
Audit log routes — read, verify, create signed checkpoints, and export the hash-chained ledger.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.audit import (
    AuditCheckpointResponse,
    AuditEntryResponse,
    AuditExportResponse,
    AuditIntegrityResponse,
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
    summary="Verify the integrity of the audit hash chain and signed checkpoint",
)
async def verify_audit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await audit_service.verify_audit_checkpoint(db)
    is_valid = bool(
        report["chain_valid"]
        and (report["checkpoint_valid"] is not False)
        and (report["signature_valid"] is not False)
    )

    return AuditVerifyResponse(
        valid=is_valid,
        entries_checked=report["entries_checked"],
        broken_at_index=report["broken_at_index"],
        chain_valid=report["chain_valid"],
        checkpoint_valid=report["checkpoint_valid"],
        signature_valid=report["signature_valid"],
        head_hash=report["head_hash"],
        broken_expected_hash=report.get("broken_expected_hash"),
        broken_stored_hash=report.get("broken_stored_hash"),
        checkpoint=report.get("checkpoint"),
        verified_at=report["verified_at"],
    )


@router.get(
    "/integrity",
    response_model=AuditIntegrityResponse,
    summary="Detailed cryptographic integrity report for audit chain and signed checkpoint",
)
async def audit_integrity(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await audit_service.verify_audit_checkpoint(db)
    is_valid = bool(
        report["chain_valid"]
        and (report["checkpoint_valid"] is not False)
        and (report["signature_valid"] is not False)
    )

    return AuditIntegrityResponse(
        status="VERIFIED" if is_valid else "COMPROMISED",
        algorithm="SHA-256",
        entries_checked=report["entries_checked"],
        chain_valid=report["chain_valid"],
        checkpoint_valid=report["checkpoint_valid"] is not False,
        signature_valid=report["signature_valid"] is not False,
        head_hash=report["head_hash"],
        broken_at_index=report["broken_at_index"],
        broken_expected_hash=report.get("broken_expected_hash"),
        broken_stored_hash=report.get("broken_stored_hash"),
        checkpoint=report.get("checkpoint"),
        verified_at=report["verified_at"],
    )


@router.post(
    "/checkpoint",
    response_model=AuditCheckpointResponse,
    summary="Generate an on-demand Ed25519 signed cryptographic checkpoint",
)
async def create_checkpoint(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async with audit_service.audit_transaction(db):
        checkpoint = await audit_service.create_checkpoint(db)
        await db.commit()

    return AuditCheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        created_at=checkpoint.created_at,
        entry_count=checkpoint.entry_count,
        head_hash=checkpoint.head_hash,
        signature=checkpoint.signature,
        key_id=checkpoint.key_id,
    )


@router.get(
    "/export",
    response_model=AuditExportResponse,
    summary="Export the full audit ledger with cryptographic checkpoint and algorithm metadata",
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

    return AuditExportResponse(
        exportTimestamp=result["exportTimestamp"],
        system=result["system"],
        algorithm=result.get("algorithm", "SHA-256"),
        genesisHash=result["genesisHash"],
        currentHeadHash=result["currentHeadHash"],
        entryCount=result["entryCount"],
        checkpoint=result.get("checkpoint"),
        operator=operator_info,
        ledger=result["ledger"],
    )
