"""
Audit log request/response schemas.
Field names intentionally match the existing frontend's audit entry shape
(index, timestamp, event, detail, hash, prevHash) so a later phase can
point renderAuditLog() at this endpoint with minimal changes.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEntryResponse(BaseModel):
    index: int = Field(..., validation_alias="idx", serialization_alias="index")
    timestamp: datetime
    event: str = Field(..., validation_alias="event_type", serialization_alias="event")
    detail: str
    hash: str
    prevHash: str = Field(..., validation_alias="prev_hash", serialization_alias="prevHash")

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditListResponse(BaseModel):
    entries: list[AuditEntryResponse]
    next_cursor: str | None = None


class AuditCheckpointResponse(BaseModel):
    checkpoint_id: str
    created_at: datetime
    entry_count: int
    head_hash: str
    signature: str
    key_id: str

    model_config = {"from_attributes": True}


class AuditVerifyResponse(BaseModel):
    valid: bool
    entries_checked: int
    broken_at_index: int | None = None
    chain_valid: bool | None = None
    checkpoint_valid: bool | None = None
    signature_valid: bool | None = None
    head_hash: str | None = None
    broken_expected_hash: str | None = None
    broken_stored_hash: str | None = None
    checkpoint: dict[str, Any] | None = None
    verified_at: str | None = None


class AuditIntegrityResponse(BaseModel):
    status: str
    algorithm: str = "SHA-256"
    entries_checked: int
    chain_valid: bool
    checkpoint_valid: bool
    signature_valid: bool
    head_hash: str
    broken_at_index: int | None = None
    broken_expected_hash: str | None = None
    broken_stored_hash: str | None = None
    checkpoint: dict[str, Any] | None = None
    verified_at: str


class AuditExportResponse(BaseModel):
    exportTimestamp: str
    system: str
    algorithm: str = "SHA-256"
    genesisHash: str
    currentHeadHash: str
    entryCount: int
    checkpoint: dict[str, Any] | None = None
    operator: dict[str, Any] | None = None
    ledger: list[AuditEntryResponse]

