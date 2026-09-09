"""
Database seed script — creates the three demo operators and the
genesis audit entry on first run.

Dev password is drawn from the SEED_PASSWORD env var, never
hardcoded in application code.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.services.audit_service import append_entry, audit_transaction

logger = logging.getLogger(__name__)

# ── Seed data ─────────────────────────────────────────────────

SEED_OPERATORS = [
    {
        "full_name": "Suketu Patel",
        "email": "suketu.2005@gmail.com",
        "role": "Chief_Safety_Auditor",
        "clearance_level": 3,
        "clearance_name": "Level 3 — Chief Safety Auditor · All Systems",
        "tier": "chief",
        "avatar": None,
    },
    {
        "full_name": "John Morrison",
        "email": "j.morrison@plant.internal",
        "role": "Maintenance_Engineer",
        "clearance_level": 1,
        "clearance_name": "Level 1 — boiler-102 only",
        "tier": "standard",
        "avatar": None,
    },
    {
        "full_name": "Dr. Elena Vance",
        "email": "elena.vance@plant.internal",
        "role": "Systems_Specialist",
        "clearance_level": 2,
        "clearance_name": "Level 2 — Turbines, Boilers, Pumps",
        "tier": "specialist",
        "avatar": None,
    },
]


async def seed_database(db: AsyncSession) -> None:
    """
    Seed demo operators and genesis audit entry.
    Uses conflict-free idempotent upsert (ON CONFLICT (email) DO NOTHING)
    so concurrent multi-worker processes never race or fail on startup.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from app.models.audit import AuditEntry

    bind = db.get_bind()
    is_pg = bool(bind and bind.dialect.name == "postgresql")
    insert_fn = pg_insert if is_pg else sqlite_insert

    password_hash = hash_password(settings.SEED_PASSWORD)

    for op in SEED_OPERATORS:
        stmt = insert_fn(User).values(
            full_name=op["full_name"],
            email=op["email"],
            password_hash=password_hash,
            role=op["role"],
            clearance_level=op["clearance_level"],
            clearance_name=op["clearance_name"],
            tier=op["tier"],
            avatar=op["avatar"],
        ).on_conflict_do_nothing(index_elements=["email"])
        await db.execute(stmt)

    await db.flush()

    # Genesis audit entry — check if table already has entries
    result = await db.execute(select(AuditEntry).limit(1))
    if result.scalars().first() is None:
        async with audit_transaction(db):
            # Double check inside the serialized lock
            res2 = await db.execute(select(AuditEntry).limit(1))
            if res2.scalars().first() is None:
                await append_entry(
                    db=db,
                    event_type="GENESIS",
                    detail="Sovereign Workbench audit chain initialized",
                    actor_user_id=None,
                )
                await db.commit()
    else:
        await db.commit()

    logger.info("Database seed completed successfully.")
