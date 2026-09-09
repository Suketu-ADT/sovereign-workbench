"""Initial schema — users and audit_log tables

Revision ID: 0001
Revises: 
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users table ───────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("clearance_level", sa.Integer, nullable=False),
        sa.Column("clearance_name", sa.String(200), nullable=False),
        sa.Column("tier", sa.String(50), nullable=True),
        sa.Column("avatar", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── Audit log table (append-only) ─────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idx", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("detail", sa.Text, nullable=False, server_default=""),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_log_idx", "audit_log", ["idx"], unique=True)

    # ── Revoke UPDATE/DELETE on audit_log ─────────────────────
    # Second line of defense — even if app code is compromised,
    # the DB role cannot modify the audit chain.
    # Note: This assumes the app connects as role 'sovereign'.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM sovereign;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT UPDATE, DELETE ON audit_log TO sovereign;")
    op.drop_index("ix_audit_log_idx")
    op.drop_table("audit_log")
    op.drop_index("ix_users_email")
    op.drop_table("users")
