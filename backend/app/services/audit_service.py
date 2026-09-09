"""
Hash-chained audit service — append-only writer and verifier.

This is the SINGLE code path that writes to the audit_log table.
No endpoint writes directly — all audit writes go through
`append_entry()` to keep the chain-building logic centralized.

Hash formula:
  hash_n = SHA256(prev_hash + "|" + canonical_json({
      index, timestamp, event_type, detail, actor_user_id
  }))

Where canonical_json uses sorted keys and no whitespace for
reproducible verification.
"""

import asyncio
import hashlib
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEntry

# 64 zero characters — the genesis entry's prev_hash
GENESIS_PREV_HASH = "0" * 64

# Fixed 64-bit key for PostgreSQL transaction-level advisory locking
AUDIT_ADVISORY_LOCK_ID = 4242424242

_chain_lock = asyncio.Lock()


@asynccontextmanager
async def audit_transaction(db: AsyncSession | None = None):
    """
    Async context manager that serializes hash-chain updates across the entire
    select -> compute -> insert -> commit sequence to prevent chain forks.

    In PostgreSQL (multi-worker/multi-instance production), acquires a database-level
    pg_advisory_xact_lock() that automatically releases on commit or rollback.
    In SQLite (local dev & tests), uses an in-process asyncio.Lock().
    """
    async with _chain_lock:
        if db is not None:
            try:
                bind = db.get_bind()
                if bind and bind.dialect.name == "postgresql":
                    await db.execute(
                        text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": AUDIT_ADVISORY_LOCK_ID},
                    )
            except Exception:
                pass
        yield


def _canonical_json(data: dict) -> str:
    """
    Produce canonical JSON: sorted keys, no whitespace, consistent
    serialization of UUIDs and datetimes.
    """
    def _default(obj):
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            else:
                obj = obj.astimezone(timezone.utc)
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def _compute_hash(prev_hash: str, entry_data: dict) -> str:
    """Compute SHA-256 hash for an audit entry."""
    canonical = _canonical_json(entry_data)
    payload = f"{prev_hash}|{canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def append_entry(
    db: AsyncSession,
    event_type: str,
    detail: str,
    actor_user_id: uuid.UUID | None = None,
) -> AuditEntry:
    """
    Append a new hash-chained entry to the audit log.

    Reads the current head of the chain, computes the next hash,
    and inserts the new entry — all within the caller's transaction.
    """
    if not _chain_lock.locked():
        raise RuntimeError(
            "append_entry() must be called within an audit_transaction() context"
        )

    # Get the latest entry to chain from
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.desc()).limit(1)
    )
    latest = result.scalars().first()

    if latest is None:
        new_idx = 0
        prev_hash = GENESIS_PREV_HASH
    else:
        new_idx = latest.idx + 1
        prev_hash = latest.hash

    now = datetime.now(timezone.utc)

    entry_data = {
        "index": new_idx,
        "timestamp": now,
        "event_type": event_type,
        "detail": detail,
        "actor_user_id": actor_user_id,
    }

    new_hash = _compute_hash(prev_hash, entry_data)

    entry = AuditEntry(
        idx=new_idx,
        timestamp=now,
        event_type=event_type,
        detail=detail,
        actor_user_id=actor_user_id,
        prev_hash=prev_hash,
        hash=new_hash,
    )
    db.add(entry)
    await db.flush()

    return entry


async def verify_chain(db: AsyncSession) -> tuple[bool, int, int | None]:
    """
    Verify the entire audit hash chain.

    Returns (valid, entries_checked, broken_at_index).
    If the chain is intact, broken_at_index is None.
    """
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.asc())
    )
    entries = result.scalars().all()

    if not entries:
        return (True, 0, None)

    for i, entry in enumerate(entries):
        # Determine expected prev_hash
        if i == 0:
            expected_prev = GENESIS_PREV_HASH
        else:
            expected_prev = entries[i - 1].hash

        if entry.prev_hash != expected_prev:
            return (False, i + 1, entry.idx)

        # Recompute hash
        entry_data = {
            "index": entry.idx,
            "timestamp": entry.timestamp,
            "event_type": entry.event_type,
            "detail": entry.detail,
            "actor_user_id": entry.actor_user_id,
        }
        expected_hash = _compute_hash(expected_prev, entry_data)

        if entry.hash != expected_hash:
            return (False, i + 1, entry.idx)

    return (True, len(entries), None)


async def get_entries(
    db: AsyncSession, limit: int = 50, cursor: int | None = None
) -> tuple[list[AuditEntry], str | None]:
    """
    Paginated retrieval of audit entries (newest first).

    `cursor` is the idx to start after (exclusive).
    Returns (entries, next_cursor).
    """
    query = select(AuditEntry).order_by(AuditEntry.idx.desc())

    if cursor is not None:
        query = query.where(AuditEntry.idx < cursor)

    query = query.limit(limit + 1)  # Fetch one extra to detect next page

    result = await db.execute(query)
    entries = list(result.scalars().all())

    next_cursor = None
    if len(entries) > limit:
        entries = entries[:limit]
        next_cursor = str(entries[-1].idx)

    return entries, next_cursor


async def export_ledger(
    db: AsyncSession, operator: dict | None = None
) -> dict:
    """
    Export the full audit ledger in the shape the frontend expects.
    """
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.asc())
    )
    entries = result.scalars().all()

    count_result = await db.execute(select(func.count(AuditEntry.id)))
    total = count_result.scalar() or 0

    genesis_hash = entries[0].hash if entries else GENESIS_PREV_HASH
    head_hash = entries[-1].hash if entries else GENESIS_PREV_HASH

    return {
        "exportTimestamp": datetime.now(timezone.utc).isoformat(),
        "system": "Sovereign Workbench — Phase 1 Backend",
        "genesisHash": genesis_hash,
        "currentHeadHash": head_hash,
        "entryCount": total,
        "operator": operator,
        "ledger": entries,
    }
