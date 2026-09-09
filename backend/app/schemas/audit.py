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


class AuditVerifyResponse(BaseModel):
    valid: bool
    entries_checked: int
    broken_at_index: int | None = None


class AuditExportResponse(BaseModel):
    exportTimestamp: str
    system: str
    genesisHash: str
    currentHeadHash: str
    entryCount: int
    operator: dict[str, Any] | None = None
    ledger: list[AuditEntryResponse]
