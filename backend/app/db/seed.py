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
from app.services.audit_service import append_entry

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
    Seed demo operators and genesis audit entry if the users table
    is empty. Safe to call on every startup — no-ops if data exists.
    """
    result = await db.execute(select(User).limit(1))
    if result.scalars().first() is not None:
        logger.info("Database already seeded — skipping.")
        return

    password_hash = hash_password(settings.SEED_PASSWORD)

    for op in SEED_OPERATORS:
        user = User(
            full_name=op["full_name"],
            email=op["email"],
            password_hash=password_hash,
            role=op["role"],
            clearance_level=op["clearance_level"],
            clearance_name=op["clearance_name"],
            tier=op["tier"],
            avatar=op["avatar"],
        )
        db.add(user)
        logger.info("Seeded operator: %s (%s)", op["full_name"], op["email"])

    await db.flush()

    # Genesis audit entry
    await append_entry(
        db=db,
        event_type="GENESIS",
        detail="Sovereign Workbench audit chain initialized",
        actor_user_id=None,
    )

    await db.commit()
    logger.info("Database seeded successfully with %d operators.", len(SEED_OPERATORS))
