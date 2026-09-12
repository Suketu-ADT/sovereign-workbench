"""Create audit_checkpoints table for Ed25519 signed tamper-evident checkpoints

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("checkpoint_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("entry_count", sa.Integer, nullable=False),
        sa.Column("head_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text, nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_checkpoints_id", "audit_checkpoints", ["checkpoint_id"], unique=True)
    op.create_index("ix_audit_checkpoints_entry_count", "audit_checkpoints", ["entry_count"])

    # Revoke UPDATE/DELETE on audit_checkpoints table in PostgreSQL (append-only ledger protection)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_checkpoints FROM sovereign;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT UPDATE, DELETE ON audit_checkpoints TO sovereign;")
    op.drop_index("ix_audit_checkpoints_entry_count", table_name="audit_checkpoints")
    op.drop_index("ix_audit_checkpoints_id", table_name="audit_checkpoints")
    op.drop_table("audit_checkpoints")
