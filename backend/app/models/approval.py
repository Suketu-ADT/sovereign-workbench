"""
Pending approval model — persistent storage for HITL workflows.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    thread_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    requestor_user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    operator_email: Mapped[str] = mapped_column(String(254), nullable=False)
    clearance_level: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    authority: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
