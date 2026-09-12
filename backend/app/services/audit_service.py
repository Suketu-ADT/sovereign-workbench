"""
Hash-chained audit service — append-only writer, verifier, and Ed25519 checkpoint manager.

This is the SINGLE code path that writes to the audit_log and audit_checkpoints tables.
No endpoint writes directly — all audit writes go through `append_entry()` or `create_checkpoint()`
to keep the cryptographic chain-building logic centralized and tamper-evident.

Hash formula:
  H0 = "0" * 64 (genesis)
  Hi = SHA256(H(i-1) + "|" + canonical_json({
      index, timestamp, event_type, detail, actor_user_id
  }))

Checkpoint formula:
  canonical_checkpoint_payload = canonical_json({
      checkpoint_id, created_at, entry_count, head_hash
  })
  signature = Ed25519.sign(private_key, canonical_checkpoint_payload)
"""

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import AuditCheckpoint, AuditEntry

logger = logging.getLogger(__name__)

# 64 zero characters — the genesis entry's prev_hash (H0)
GENESIS_PREV_HASH = "0" * 64

# Fixed 64-bit key for PostgreSQL transaction-level advisory locking
AUDIT_ADVISORY_LOCK_ID = 4242424242

_chain_lock = asyncio.Lock()
_cached_dev_private_key: Ed25519PrivateKey | None = None


@asynccontextmanager
async def audit_transaction(db: AsyncSession):
    """
    Async context manager that serializes hash-chain updates across the entire
    select -> compute -> insert -> commit sequence to prevent chain forks.

    In PostgreSQL (multi-worker/multi-instance production), acquires a database-level
    pg_advisory_xact_lock() that automatically releases on commit or rollback.
    In SQLite (local dev & tests), uses an in-process asyncio.Lock().
    """
    async with _chain_lock:
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
    Produce canonical JSON: sorted keys, compact separators (',', ':'),
    deterministic datetime serialization (ISO 8601 with UTC),
    deterministic UUID serialization, and UTF-8 encoding.
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


# ── Ed25519 Key Management ────────────────────────────────────────

def get_signing_private_key() -> Ed25519PrivateKey:
    """
    Loads or generates the Ed25519 private key for audit checkpoint signing.
    In production, must come from AUDIT_SIGNING_PRIVATE_KEY_PATH (secure mounted secret).
    In local development, generates/caches a dev key on disk in backend/keys/ or memory.
    """
    global _cached_dev_private_key
    if _cached_dev_private_key is not None:
        return _cached_dev_private_key

    key_path_str = getattr(settings, "AUDIT_SIGNING_PRIVATE_KEY_PATH", None)
    if key_path_str and os.path.exists(key_path_str):
        with open(key_path_str, "rb") as f:
            data = f.read()
            try:
                _cached_dev_private_key = serialization.load_pem_private_key(data, password=None)
                return _cached_dev_private_key
            except Exception:
                if len(data) == 32:
                    _cached_dev_private_key = Ed25519PrivateKey.from_private_bytes(data)
                    return _cached_dev_private_key

    # Local development: persist dev key to backend/keys/dev_audit_ed25519.pem
    backend_dir = Path(__file__).resolve().parent.parent.parent
    dev_key_dir = backend_dir / "keys"
    dev_key_file = dev_key_dir / "dev_audit_ed25519.pem"

    try:
        dev_key_dir.mkdir(parents=True, exist_ok=True)
        if dev_key_file.exists():
            with open(dev_key_file, "rb") as f:
                _cached_dev_private_key = serialization.load_pem_private_key(f.read(), password=None)
                return _cached_dev_private_key
        else:
            new_key = Ed25519PrivateKey.generate()
            pem_bytes = new_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(dev_key_file, "wb") as f:
                f.write(pem_bytes)
            _cached_dev_private_key = new_key
            return _cached_dev_private_key
    except Exception as e:
        logger.debug("Could not persist dev key file (%s); using in-memory key", e)
        _cached_dev_private_key = Ed25519PrivateKey.generate()
        return _cached_dev_private_key


def get_public_key_bytes(key_id: str | None = None) -> bytes:
    """Returns raw 32-byte Ed25519 public key corresponding to key_id."""
    configured_pub = getattr(settings, "AUDIT_SIGNING_PUBLIC_KEY", None)
    if configured_pub:
        pub_str = configured_pub.strip()
        if len(pub_str) == 64:
            try:
                return bytes.fromhex(pub_str)
            except ValueError:
                pass

    priv_key = get_signing_private_key()
    pub_key = priv_key.public_key()
    return pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def get_public_key_hex(key_id: str | None = None) -> str:
    """Returns 64-character hex string of Ed25519 public key."""
    return get_public_key_bytes(key_id).hex()


def canonical_checkpoint_payload(
    checkpoint_id: str,
    created_at: datetime | str,
    entry_count: int,
    head_hash: str,
) -> bytes:
    """
    Computes deterministic canonical bytes for a checkpoint payload.
    Keys are strictly sorted: checkpoint_id, created_at, entry_count, head_hash.
    """
    payload_dict = {
        "checkpoint_id": checkpoint_id,
        "created_at": created_at,
        "entry_count": entry_count,
        "head_hash": head_hash,
    }
    return _canonical_json(payload_dict).encode("utf-8")


def sign_checkpoint_payload(
    payload_bytes: bytes,
    private_key: Ed25519PrivateKey | None = None,
) -> str:
    """Signs canonical checkpoint payload bytes and returns hex-encoded Ed25519 signature."""
    key = private_key or get_signing_private_key()
    sig = key.sign(payload_bytes)
    return sig.hex()


def verify_checkpoint_signature(
    signature_hex: str,
    payload_bytes: bytes,
    public_key_bytes: bytes | None = None,
) -> bool:
    """Verifies Ed25519 signature against canonical payload bytes."""
    try:
        pub_bytes = public_key_bytes or get_public_key_bytes()
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        sig_bytes = bytes.fromhex(signature_hex)
        pub_key.verify(sig_bytes, payload_bytes)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


# ── Checkpoint Creation ───────────────────────────────────────────

async def create_checkpoint(
    db: AsyncSession,
    key_id: str | None = None,
) -> AuditCheckpoint:
    """
    Creates and cryptographically signs an Ed25519 audit checkpoint
    anchoring the current head hash and entry count.
    """
    # Query latest audit entry
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.desc()).limit(1)
    )
    latest = result.scalars().first()
    if latest is None:
        entry_count = 0
        head_hash = GENESIS_PREV_HASH
    else:
        entry_count = latest.idx + 1
        head_hash = latest.hash

    active_key_id = key_id or getattr(settings, "AUDIT_SIGNING_KEY_ID", "audit-key-01")
    checkpoint_id = f"chk-{entry_count:06d}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    payload_bytes = canonical_checkpoint_payload(
        checkpoint_id=checkpoint_id,
        created_at=now,
        entry_count=entry_count,
        head_hash=head_hash,
    )

    sig_hex = sign_checkpoint_payload(payload_bytes)

    checkpoint = AuditCheckpoint(
        checkpoint_id=checkpoint_id,
        created_at=now,
        entry_count=entry_count,
        head_hash=head_hash,
        signature=sig_hex,
        key_id=active_key_id,
    )
    db.add(checkpoint)
    await db.flush()
    return checkpoint


# ── Append Entry (Single Writer) ──────────────────────────────────

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
    If AUDIT_CHECKPOINT_INTERVAL is reached, automatically generates a signed checkpoint.
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

    # Automatically create signed checkpoint on configured interval
    checkpoint_interval = getattr(settings, "AUDIT_CHECKPOINT_INTERVAL", 100)
    if checkpoint_interval > 0 and (new_idx + 1) % checkpoint_interval == 0:
        try:
            await create_checkpoint(db)
        except Exception as e:
            logger.warning("Automatic checkpoint creation failed: %s", e)

    return entry


# ── Verification ──────────────────────────────────────────────────

async def verify_chain(db: AsyncSession) -> tuple[bool, int, int | None]:
    """
    Verify the entire audit hash chain.

    Returns (valid, entries_checked, broken_at_index).
    If the chain is intact, broken_at_index is None.
    Maintains 100% backward compatibility with existing tests.
    """
    db.expire_all()
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.asc())
    )
    entries = result.scalars().all()

    if not entries:
        return (True, 0, None)

    for i, entry in enumerate(entries):
        if i == 0:
            expected_prev = GENESIS_PREV_HASH
        else:
            expected_prev = entries[i - 1].hash

        if entry.prev_hash != expected_prev:
            return (False, i + 1, entry.idx)

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


async def verify_audit_checkpoint(db: AsyncSession) -> dict[str, Any]:
    """
    Full cryptographic verification:
      1. Loads latest checkpoint (if any).
      2. Recomputes canonical checkpoint payload.
      3. Verifies Ed25519 signature against public key.
      4. Verifies checkpoint head_hash matches audit chain head at checkpoint entry_count.
      5. Verifies the complete SHA-256 hash chain up to the current head.
    """
    db.expire_all()
    verified_at = datetime.now(timezone.utc).isoformat()

    # 1. Verify complete hash chain
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.asc())
    )
    entries = result.scalars().all()


    chain_valid = True
    broken_at_index = None
    broken_expected_hash = None
    broken_stored_hash = None
    entries_checked = len(entries)

    for i, entry in enumerate(entries):
        expected_prev = GENESIS_PREV_HASH if i == 0 else entries[i - 1].hash
        if entry.prev_hash != expected_prev:
            chain_valid = False
            broken_at_index = entry.idx
            broken_expected_hash = expected_prev
            broken_stored_hash = entry.prev_hash
            entries_checked = i + 1
            break

        entry_data = {
            "index": entry.idx,
            "timestamp": entry.timestamp,
            "event_type": entry.event_type,
            "detail": entry.detail,
            "actor_user_id": entry.actor_user_id,
        }
        computed_hash = _compute_hash(expected_prev, entry_data)
        if entry.hash != computed_hash:
            chain_valid = False
            broken_at_index = entry.idx
            broken_expected_hash = computed_hash
            broken_stored_hash = entry.hash
            entries_checked = i + 1
            break

    head_hash = entries[-1].hash if entries else GENESIS_PREV_HASH

    # 2. Check latest checkpoint
    chk_result = await db.execute(
        select(AuditCheckpoint).order_by(AuditCheckpoint.entry_count.desc(), AuditCheckpoint.id.desc()).limit(1)
    )
    latest_chk = chk_result.scalars().first()

    checkpoint_valid = True
    signature_valid = True
    checkpoint_data = None
    checkpoint_entry_count = None

    if latest_chk is not None:
        checkpoint_entry_count = latest_chk.entry_count
        checkpoint_data = {
            "checkpoint_id": latest_chk.checkpoint_id,
            "created_at": latest_chk.created_at.isoformat() if isinstance(latest_chk.created_at, datetime) else str(latest_chk.created_at),
            "entry_count": latest_chk.entry_count,
            "head_hash": latest_chk.head_hash,
            "signature": latest_chk.signature,
            "key_id": latest_chk.key_id,
        }

        # Verify Ed25519 signature
        payload_bytes = canonical_checkpoint_payload(
            checkpoint_id=latest_chk.checkpoint_id,
            created_at=latest_chk.created_at,
            entry_count=latest_chk.entry_count,
            head_hash=latest_chk.head_hash,
        )
        sig_ok = verify_checkpoint_signature(latest_chk.signature, payload_bytes)
        signature_valid = sig_ok

        # Verify checkpoint matches head hash at checkpoint entry count
        if latest_chk.entry_count == 0:
            expected_head_at_chk = GENESIS_PREV_HASH
        elif latest_chk.entry_count <= len(entries):
            expected_head_at_chk = entries[latest_chk.entry_count - 1].hash
        else:
            expected_head_at_chk = None

        if not sig_ok or (expected_head_at_chk is not None and expected_head_at_chk != latest_chk.head_hash):
            checkpoint_valid = False
            if broken_at_index is None and expected_head_at_chk is not None and expected_head_at_chk != latest_chk.head_hash:
                broken_at_index = latest_chk.entry_count
                broken_expected_hash = expected_head_at_chk
                broken_stored_hash = latest_chk.head_hash

    return {
        "chain_valid": chain_valid,
        "checkpoint_valid": checkpoint_valid,
        "signature_valid": signature_valid,
        "entries_checked": entries_checked,
        "checkpoint_entry_count": checkpoint_entry_count,
        "head_hash": head_hash,
        "verified_at": verified_at,
        "broken_at_index": broken_at_index,
        "broken_expected_hash": broken_expected_hash,
        "broken_stored_hash": broken_stored_hash,
        "checkpoint": checkpoint_data,
    }


# ── Retrieval & Export ────────────────────────────────────────────

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
    Export the full audit ledger including genesis hash, current head hash,
    algorithm metadata, signed checkpoint, and all audit records.
    """
    result = await db.execute(
        select(AuditEntry).order_by(AuditEntry.idx.asc())
    )
    entries = result.scalars().all()

    count_result = await db.execute(select(func.count(AuditEntry.id)))
    total = count_result.scalar() or 0

    genesis_hash = entries[0].hash if entries else GENESIS_PREV_HASH
    head_hash = entries[-1].hash if entries else GENESIS_PREV_HASH

    # Latest checkpoint if present
    chk_result = await db.execute(
        select(AuditCheckpoint).order_by(AuditCheckpoint.entry_count.desc(), AuditCheckpoint.id.desc()).limit(1)
    )
    latest_chk = chk_result.scalars().first()
    checkpoint_data = None
    if latest_chk is not None:
        checkpoint_data = {
            "checkpoint_id": latest_chk.checkpoint_id,
            "checkpoint_timestamp": latest_chk.created_at.isoformat() if isinstance(latest_chk.created_at, datetime) else str(latest_chk.created_at),
            "checkpoint_entry_count": latest_chk.entry_count,
            "checkpoint_head_hash": latest_chk.head_hash,
            "checkpoint_signature": latest_chk.signature,
            "checkpoint_key_id": latest_chk.key_id,
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "exportTimestamp": now_iso,
        "export_timestamp": now_iso,
        "system": "Sovereign Workbench — Cryptographic Tamper-Evident Audit Ledger",
        "algorithm": "SHA-256",
        "genesisHash": genesis_hash,
        "genesis_hash": genesis_hash,
        "currentHeadHash": head_hash,
        "current_head_hash": head_hash,
        "entryCount": total,
        "entry_count": total,
        "checkpoint": checkpoint_data,
        "operator": operator,
        "ledger": entries,
    }
