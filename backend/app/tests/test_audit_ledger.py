"""
Comprehensive Cryptographic Tamper-Evident Audit Ledger Test Suite.

Verifies:
  1. Empty chain
  2. Single event hash chain formula
  3. Multiple chained events
  4. Hash reproduction (deterministic verification)
  5. Tamper detection: modified detail
  6. Tamper detection: modified timestamp
  7. Tamper detection: modified actor
  8. Tamper detection: modified index
  9. Tamper detection: modified prev_hash
  10. Tamper detection: modified hash
  11. Tamper detection: deleted middle entry
  12. Tamper detection: reordered entries
  13. Concurrent writes (no duplicate prev_hash, sequential chain)
  14. Valid Ed25519 signed checkpoint creation and verification
  15. Tamper detection: invalid checkpoint signature
  16. Tamper detection: changed checkpoint head hash
  17. Tamper detection: audit entry changed after checkpoint
  18. Section 13 demonstration: mutate historical record, detect break, restore database state
"""

import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager
import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.models.audit import AuditCheckpoint, AuditEntry
from app.services import audit_service


@asynccontextmanager
async def get_test_db():
    """Provides an isolated in-memory SQLite database per test context."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ── Test 1: Empty Chain ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_empty_chain():
    async with get_test_db() as test_db:
        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is True
        assert checked == 0
        assert broken is None

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["chain_valid"] is True
        assert report["entries_checked"] == 0
        assert report["broken_at_index"] is None


# ── Test 2: Single Event ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_02_single_event():
    async with get_test_db() as test_db:
        async with audit_service.audit_transaction(test_db):
            entry = await audit_service.append_entry(
                test_db,
                event_type="OPERATOR_LOGIN",
                detail="Operator logged in from terminal 01",
            )
            await test_db.commit()

        assert entry.idx == 0
        assert entry.prev_hash == audit_service.GENESIS_PREV_HASH
        assert len(entry.hash) == 64

        # Verify formula manually
        expected_hash = audit_service._compute_hash(
            audit_service.GENESIS_PREV_HASH,
            {
                "index": 0,
                "timestamp": entry.timestamp,
                "event_type": "OPERATOR_LOGIN",
                "detail": "Operator logged in from terminal 01",
                "actor_user_id": None,
            }
        )
        assert entry.hash == expected_hash

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is True
        assert checked == 1
        assert broken is None


# ── Test 3: Multiple Chained Events ───────────────────────────────

@pytest.mark.asyncio
async def test_03_multiple_chained_events():
    async with get_test_db() as test_db:
        entries = []
        for i in range(5):
            async with audit_service.audit_transaction(test_db):
                e = await audit_service.append_entry(
                    test_db,
                    event_type=f"EVENT_{i}",
                    detail=f"Automated event sequence #{i}",
                )
                entries.append(e)
                await test_db.commit()

        for i in range(1, 5):
            assert entries[i].prev_hash == entries[i - 1].hash
            assert entries[i].idx == i

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is True
        assert checked == 5
        assert broken is None


# ── Test 4: Hash Reproduction ─────────────────────────────────────

@pytest.mark.asyncio
async def test_04_hash_reproduction():
    fixed_time = datetime.datetime(2026, 9, 11, 14, 30, 0, tzinfo=datetime.timezone.utc)
    fixed_actor = uuid.UUID("11111111-2222-3333-4444-555555555555")

    data = {
        "index": 42,
        "timestamp": fixed_time,
        "event_type": "PIPELINE_GUARD_VERIFIED",
        "detail": "8/8 gates passed without violation",
        "actor_user_id": fixed_actor,
    }
    prev = "a" * 64
    h1 = audit_service._compute_hash(prev, data)
    h2 = audit_service._compute_hash(prev, data)
    assert h1 == h2
    assert len(h1) == 64


# ── Test 5: Modified Detail Tampering ─────────────────────────────

@pytest.mark.asyncio
async def test_05_tamper_modified_detail():
    async with get_test_db() as test_db:
        for i in range(4):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with detail at index 2
        await test_db.execute(
            text("UPDATE audit_log SET detail = 'MALICIOUS_TAMPERED_DETAIL' WHERE idx = 2")
        )
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        assert broken == 2

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["chain_valid"] is False
        assert report["broken_at_index"] == 2


# ── Test 6: Modified Timestamp Tampering ──────────────────────────

@pytest.mark.asyncio
async def test_06_tamper_modified_timestamp():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with timestamp at index 1
        new_ts = datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        await test_db.execute(
            text("UPDATE audit_log SET timestamp = :ts WHERE idx = 1"),
            {"ts": new_ts}
        )
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        assert broken == 1


# ── Test 7: Modified Actor Tampering ──────────────────────────────

@pytest.mark.asyncio
async def test_07_tamper_modified_actor():
    async with get_test_db() as test_db:
        actor = uuid.uuid4()
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}", actor_user_id=actor)
                await test_db.commit()

        # Tamper with actor_user_id at index 1
        fake_actor = str(uuid.uuid4())
        await test_db.execute(
            text("UPDATE audit_log SET actor_user_id = :act WHERE idx = 1"),
            {"act": fake_actor}
        )
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        assert broken == 1


# ── Test 8: Modified Index Tampering ──────────────────────────────

@pytest.mark.asyncio
async def test_08_tamper_modified_index():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with index at row 2
        await test_db.execute(text("UPDATE audit_log SET idx = 99 WHERE idx = 2"))
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False


# ── Test 9: Modified Prev Hash Tampering ──────────────────────────

@pytest.mark.asyncio
async def test_09_tamper_modified_prev_hash():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with prev_hash at index 2
        fake_prev = "f" * 64
        await test_db.execute(
            text("UPDATE audit_log SET prev_hash = :p WHERE idx = 2"),
            {"p": fake_prev}
        )
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        assert broken == 2


# ── Test 10: Modified Hash Tampering ──────────────────────────────

@pytest.mark.asyncio
async def test_10_tamper_modified_hash():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with hash at index 1
        fake_hash = "c" * 64
        await test_db.execute(
            text("UPDATE audit_log SET hash = :h WHERE idx = 1"),
            {"h": fake_hash}
        )
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        assert broken == 1


# ── Test 11: Deleted Middle Entry Tampering ───────────────────────

@pytest.mark.asyncio
async def test_11_tamper_deleted_middle_entry():
    async with get_test_db() as test_db:
        for i in range(5):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Delete entry at index 2 directly
        await test_db.execute(text("DELETE FROM audit_log WHERE idx = 2"))
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False
        # Next entry (idx 3) points to deleted entry 2's hash, but its predecessor is now entry 1
        assert broken == 3


# ── Test 12: Reordered Entries Tampering ──────────────────────────

@pytest.mark.asyncio
async def test_12_tamper_reordered_entries():
    async with get_test_db() as test_db:
        for i in range(4):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Swap idx values for entries 1 and 2
        await test_db.execute(text("UPDATE audit_log SET idx = 999 WHERE idx = 1"))
        await test_db.execute(text("UPDATE audit_log SET idx = 1 WHERE idx = 2"))
        await test_db.execute(text("UPDATE audit_log SET idx = 2 WHERE idx = 999"))
        await test_db.commit()

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is False


# ── Test 13: Concurrent Writes ────────────────────────────────────

@pytest.mark.asyncio
async def test_13_concurrent_writes_serial_chain():
    """Multiple concurrent writers must produce a linear unbroken chain with no duplicate prev_hash."""
    async with get_test_db() as test_db:
        async def worker(w_id: int):
            for step in range(3):
                async with audit_service.audit_transaction(test_db):
                    await audit_service.append_entry(
                        test_db,
                        event_type=f"CONCURRENT_WORKER_{w_id}",
                        detail=f"Worker {w_id} action step {step}",
                    )
                    await test_db.commit()

        # 4 concurrent workers x 3 writes = 12 total entries
        await asyncio.gather(worker(1), worker(2), worker(3), worker(4))

        result = await test_db.execute(select(AuditEntry).order_by(AuditEntry.idx.asc()))
        entries = result.scalars().all()
        assert len(entries) == 12

        # Check indices are 0 to 11
        for idx, e in enumerate(entries):
            assert e.idx == idx

        # Check no two non-genesis entries have identical prev_hash
        prev_hashes = [e.prev_hash for e in entries[1:]]
        assert len(prev_hashes) == len(set(prev_hashes)), "Duplicate prev_hash detected in concurrent writes!"

        valid, checked, broken = await audit_service.verify_chain(test_db)
        assert valid is True
        assert checked == 12
        assert broken is None


# ── Test 14: Valid Signed Checkpoint ──────────────────────────────

@pytest.mark.asyncio
async def test_14_valid_checkpoint():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        async with audit_service.audit_transaction(test_db):
            checkpoint = await audit_service.create_checkpoint(test_db)
            await test_db.commit()

        assert checkpoint.entry_count == 3
        assert len(checkpoint.head_hash) == 64
        assert len(checkpoint.signature) == 128  # 64-byte Ed25519 signature in hex

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["chain_valid"] is True
        assert report["checkpoint_valid"] is True
        assert report["signature_valid"] is True
        assert report["checkpoint_entry_count"] == 3


# ── Test 15: Invalid Checkpoint Signature Tampering ───────────────

@pytest.mark.asyncio
async def test_15_invalid_checkpoint_signature():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        async with audit_service.audit_transaction(test_db):
            chk = await audit_service.create_checkpoint(test_db)
            await test_db.commit()

        # Tamper with checkpoint signature
        bad_sig = "a" * 128
        await test_db.execute(
            text("UPDATE audit_checkpoints SET signature = :sig WHERE id = :cid"),
            {"sig": bad_sig, "cid": chk.id}
        )
        await test_db.commit()

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["signature_valid"] is False
        assert report["checkpoint_valid"] is False


# ── Test 16: Changed Checkpoint Head Hash Tampering ───────────────

@pytest.mark.asyncio
async def test_16_changed_checkpoint_head_hash():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        async with audit_service.audit_transaction(test_db):
            chk = await audit_service.create_checkpoint(test_db)
            await test_db.commit()

        # Mutate head_hash in checkpoint record
        fake_head = "e" * 64
        await test_db.execute(
            text("UPDATE audit_checkpoints SET head_hash = :h WHERE id = :cid"),
            {"h": fake_head, "cid": chk.id}
        )
        await test_db.commit()

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["checkpoint_valid"] is False


# ── Test 17: Audit Entry Changed After Checkpoint ─────────────────

@pytest.mark.asyncio
async def test_17_changed_audit_record_after_checkpoint():
    async with get_test_db() as test_db:
        for i in range(3):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        async with audit_service.audit_transaction(test_db):
            await audit_service.create_checkpoint(test_db)
            await test_db.commit()

        # Append 2 more entries
        for i in range(3, 5):
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"TYPE_{i}", f"Detail {i}")
                await test_db.commit()

        # Tamper with entry at idx 1 (which was part of the signed checkpoint range)
        await test_db.execute(
            text("UPDATE audit_log SET detail = 'TAMPERED_PRE_CHECKPOINT' WHERE idx = 1")
        )
        await test_db.commit()

        report = await audit_service.verify_audit_checkpoint(test_db)
        assert report["chain_valid"] is False
        assert report["broken_at_index"] == 1


# ── Test 18: Section 13 Demonstration: Tamper & Restore ───────────

@pytest.mark.asyncio
async def test_18_demonstration_tamper_and_restore():
    """
    Requirement 13:
    1. Populate historical ledger.
    2. Verify chain is pristine.
    3. Modify historical detail ('Original event' -> 'Tampered event').
    4. Assert verify_chain detects failure at exact broken_at_index.
    5. Restore original database state.
    6. Assert verify_chain passes with 100% integrity.
    """
    async with get_test_db() as test_db:
        original_detail = "Original event"
        tampered_detail = "Tampered event"

        for i in range(5):
            d = original_detail if i == 2 else f"Event #{i}"
            async with audit_service.audit_transaction(test_db):
                await audit_service.append_entry(test_db, f"EVENT_{i}", d)
                await test_db.commit()

        # Pristine check
        v0, c0, b0 = await audit_service.verify_chain(test_db)
        assert v0 is True
        assert c0 == 5
        assert b0 is None

        # Step A: Tamper historical entry 2
        await test_db.execute(
            text("UPDATE audit_log SET detail = :t WHERE idx = 2"),
            {"t": tampered_detail}
        )
        await test_db.commit()

        # Step B: Verifier must detect break at block 2
        v1, c1, b1 = await audit_service.verify_chain(test_db)
        assert v1 is False
        assert b1 == 2, f"Expected broken_at_index 2, got {b1}"

        # Step C: Restore original state
        await test_db.execute(
            text("UPDATE audit_log SET detail = :o WHERE idx = 2"),
            {"o": original_detail}
        )
        await test_db.commit()

        # Step D: Verifier must pass completely again
        v2, c2, b2 = await audit_service.verify_chain(test_db)
        assert v2 is True
        assert c2 == 5
        assert b2 is None


# ── Test 19 & 20: HTTP API Endpoint Integration ───────────────────

@pytest.mark.asyncio
async def test_19_api_audit_endpoints():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(uuid.uuid4()),
        "email": "auditor@plant.internal",
        "role": "Chief_Safety_Auditor",
        "clearance_level": 3,
        "clearance_name": "Level 3 Auditor",
    })
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /audit
        r_list = await client.get("/audit", headers=headers)
        assert r_list.status_code == 200
        assert "entries" in r_list.json()

        # 2. POST /audit/checkpoint
        r_chk = await client.post("/audit/checkpoint", headers=headers)
        assert r_chk.status_code == 200
        chk_data = r_chk.json()
        assert "checkpoint_id" in chk_data
        assert "signature" in chk_data
        assert len(chk_data["signature"]) == 128

        # 3. GET /audit/verify
        r_ver = await client.get("/audit/verify", headers=headers)
        assert r_ver.status_code == 200
        ver_data = r_ver.json()
        assert "valid" in ver_data
        assert "chain_valid" in ver_data
        assert "checkpoint_valid" in ver_data

        # 4. GET /audit/integrity
        r_int = await client.get("/audit/integrity", headers=headers)
        assert r_int.status_code == 200
        int_data = r_int.json()
        assert int_data["status"] in ("VERIFIED", "COMPROMISED")
        assert int_data["algorithm"] == "SHA-256"

        # 5. GET /audit/export
        r_exp = await client.get("/audit/export", headers=headers)
        assert r_exp.status_code == 200
        exp_data = r_exp.json()
        assert exp_data["algorithm"] == "SHA-256"
        assert "genesisHash" in exp_data
        assert "currentHeadHash" in exp_data
        assert "ledger" in exp_data

