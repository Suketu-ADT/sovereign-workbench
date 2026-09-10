"""
Custom database types for SQLAlchemy.
"""

import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """
    Platform-independent GUID/UUID type.
    Uses PostgreSQL's native UUID type where available, otherwise CHAR(36)
    storing canonical string representation with hyphens.
    This avoids SQLite NUMERIC affinity issues where all-digit UUID hex strings
    (e.g. '11111111111111111111111111111111') are coerced into floating-point numbers.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, AttributeError):
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            try:
                # Handle edge case where SQLite coerced numeric hex into float
                return uuid.UUID(hex(int(value))[2:].zfill(32))
            except Exception:
                return None
