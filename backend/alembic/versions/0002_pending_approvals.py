"""Create pending_approvals table for persistent HITL state

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_approvals",
        sa.Column("thread_id", sa.String(100), primary_key=True),
        sa.Column("requestor_user_id", sa.Uuid(), nullable=False),
        sa.Column("operator_email", sa.String(254), nullable=False),
        sa.Column("clearance_level", sa.Integer, nullable=False),
        sa.Column("unit", sa.String(100), nullable=False),
        sa.Column("authority", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("approval_details", sa.JSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pending_approvals_status", "pending_approvals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pending_approvals_status", table_name="pending_approvals")
    op.drop_table("pending_approvals")
