"""
Phase 7 Automated Test Suite — Comprehensive Security Review, Boundary Hardening,
Cryptographic Tamper-Detection Proof, and Multi-Operator E2E Journey.
"""

import base64
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.services import audit_service, calculation_service, vision_service


@pytest.mark.asyncio
async def test_input_length_and_null_byte_rejected():
    """Verifies that oversized inputs (>4096 chars) and null-byte injection are rejected with HTTP 422."""
    transport = ASGITransport(app=app)
    token = create_access_token({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "j.morrison@plant.internal",
        "clearance_level": 1,
        "role": "Maintenance_Engineer",
    })

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Oversized payload (4097 chars)
        long_text = "boiler-102 " + ("A" * 4100)
        res_long = await ac.post(
            "/query",
            json={"text": long_text, "has_image": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_long.status_code == 422, f"Expected 422 for oversized text, got {res_long.status_code}"

        # 2. Null-byte injection
        null_byte_text = "boiler-102 \x00 drop table audit_log;"
        res_null = await ac.post(
            "/query",
            json={"text": null_byte_text, "has_image": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_null.status_code == 422, f"Expected 422 for null-byte payload, got {res_null.status_code}"


@pytest.mark.asyncio
async def test_corrupted_image_magic_bytes_rejected():
    """Verifies that non-image payloads fail magic byte validation and do not cause uncaught crashes."""
    # Test vision service byte decoding directly: invalid magic header rejected
    fake_image_bytes = b"NOT_A_REAL_IMAGE_HEADER_CONTENT_AT_ALL"
    decoded_img = vision_service._decode_image_bytes(fake_image_bytes)
    assert decoded_img is None, "Expected invalid magic bytes to fail image decoding safely"

    fake_b64 = base64.b64encode(fake_image_bytes).decode("ascii")
    result = await vision_service.extract_gauge_reading(fake_b64)
    assert result is not None
    assert result.status == "invalid_image"
    assert result.reading is None
    assert result.error is not None

    # Test via query endpoint with corrupted image base64
    transport = ASGITransport(app=app)
    token = create_access_token({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "j.morrison@plant.internal",
        "clearance_level": 1,
        "role": "Maintenance_Engineer",
    })

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query",
            json={
                "text": "Read boiler-102 gauge pressure",
                "has_image": True,
                "image_data": fake_b64,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Query endpoint handles corrupted vision payload gracefully without 500
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("accepted_stub", "awaiting_approval")
        assert data["vision_analysis"] is not None
        assert data["vision_analysis"]["status"] == "invalid_image"
        assert data["vision_analysis"]["reading"] is None
        assert data["calculation_result"] is None



@pytest.mark.asyncio
async def test_cryptographic_tamper_detection_proof():
    """
    Rigorously proves tamper-evidence:
    1. Verify initial hash chain integrity.
    2. Directly mutate a historical row in the SQLite database via raw SQL.
    3. Assert verify_chain detects the exact broken index and SHA-256 mismatch.
    """
    transport = ASGITransport(app=app)
    admin_token = create_access_token({
        "sub": "33333333-3333-3333-3333-333333333333",
        "email": "s.patel@plant.internal",
        "clearance_level": 3,
        "role": "Plant_Director",
    })

    async with async_session_factory() as db:
        # Ensure at least 3 entries exist
        async with audit_service.audit_transaction(db):
            await audit_service.append_entry(db, "SECURITY_TEST_1", "Initial benchmark entry")
            await audit_service.append_entry(db, "SECURITY_TEST_2", "Second chained entry")
            await audit_service.append_entry(db, "SECURITY_TEST_3", "Third chained entry")
            await db.commit()

        # Step 1: Initial chain must be fully valid
        valid, count, broken_idx = await audit_service.verify_chain(db)
        assert valid is True
        assert broken_idx is None
        assert count >= 3

        # Pick an index to tamper with (e.g. index 1)
        target_tamper_idx = 1

        # Step 2: Mutate the row directly in SQLite bypassing the audit service
        await db.execute(
            text(f"UPDATE audit_log SET detail = 'MALICIOUS_TAMPERED_PAYLOAD' WHERE idx = {target_tamper_idx}")
        )
        await db.commit()

        # Step 3: Direct service verify_chain must detect the tamper at target_tamper_idx
        tampered_valid, tampered_count, tampered_broken_idx = await audit_service.verify_chain(db)
        assert tampered_valid is False, "Audit chain failed to detect direct database tampering!"
        assert tampered_broken_idx == target_tamper_idx, f"Expected broken index {target_tamper_idx}, got {tampered_broken_idx}"

    # Step 4: Endpoint /audit/verify must report the broken chain
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/audit/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        verify_data = res.json()
        assert verify_data["valid"] is False
        assert verify_data["broken_at_index"] == target_tamper_idx


@pytest.mark.asyncio
async def test_e2e_multi_operator_journey():
    """
    Simulates a multi-operator plant shift journey across clearance tiers (L1, L2, L3)
    and validates authorization boundaries and Human-In-The-Loop approvals.
    """
    transport = ASGITransport(app=app)

    token_l1 = create_access_token({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "j.morrison@plant.internal",
        "clearance_level": 1,
        "role": "Maintenance_Engineer",
    })
    token_l2 = create_access_token({
        "sub": "22222222-2222-2222-2222-222222222222",
        "email": "e.vance@plant.internal",
        "clearance_level": 2,
        "role": "Operations_Lead",
    })
    token_l3 = create_access_token({
        "sub": "33333333-3333-3333-3333-333333333333",
        "email": "s.patel@plant.internal",
        "clearance_level": 3,
        "role": "Plant_Director",
    })

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Operator 1 (L1) accesses boiler-102 -> OK
        res1 = await ac.post(
            "/query",
            json={"text": "Check boiler-102 status", "has_image": False},
            headers={"Authorization": f"Bearer {token_l1}"},
        )
        assert res1.status_code == 200
        assert res1.json()["status"] in ("accepted_stub", "awaiting_approval")

        # Operator 1 (L1) tries turbine-gen-4 -> Blocked (403)
        res1_denied = await ac.post(
            "/query",
            json={"text": "Check turbine-gen-4 bearing vibration", "has_image": False},
            headers={"Authorization": f"Bearer {token_l1}"},
        )
        assert res1_denied.status_code == 403

        # Operator 2 (L2) accesses turbine-gen-4 -> OK
        res2 = await ac.post(
            "/query",
            json={"text": "Check turbine-gen-4 bearing vibration", "has_image": False},
            headers={"Authorization": f"Bearer {token_l2}"},
        )
        assert res2.status_code == 200
        assert res2.json()["status"] in ("accepted_stub", "awaiting_approval")

        # Operator 2 (L2) tries reactor-core-aux -> Blocked (403)
        res2_denied = await ac.post(
            "/query",
            json={"text": "Check reactor-core-aux coolant flow", "has_image": False},
            headers={"Authorization": f"Bearer {token_l2}"},
        )
        assert res2_denied.status_code == 403

        # Operator 3 (L3) accesses reactor-core-aux -> OK
        res3 = await ac.post(
            "/query",
            json={"text": "Check reactor-core-aux coolant flow", "has_image": False},
            headers={"Authorization": f"Bearer {token_l3}"},
        )
        assert res3.status_code == 200
        assert res3.json()["status"] in ("accepted_stub", "awaiting_approval")

        # Operator 2 (L2) triggers sensitive actuator command -> HITL interruption
        res_actuator = await ac.post(
            "/query",
            json={"text": "Emergency: adjust_governor on turbine-gen-4 immediately", "has_image": False, "unit": "turbine-gen-4"},
            headers={"Authorization": f"Bearer {token_l2}"},
        )
        assert res_actuator.status_code == 200
        actuator_data = res_actuator.json()
        assert actuator_data.get("status") == "awaiting_approval" or actuator_data.get("planner_result", {}).get("approval_required") is True
        assert actuator_data.get("approval_id") is not None or actuator_data.get("approval_details") is not None
        thread_id = actuator_data.get("approval_id") or actuator_data["approval_details"]["thread_id"]

        # Fetch pending approvals (L3)
        res_pending = await ac.get(
            "/approvals/pending",
            headers={"Authorization": f"Bearer {token_l3}"},
        )
        assert res_pending.status_code == 200
        pending_items = res_pending.json()["approvals"]
        assert any(item["thread_id"] == thread_id for item in pending_items)

        # Operator 3 approves the action
        res_decision = await ac.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "APPROVE", "comment": "Operator confirmed safety bypass"},
            headers={"Authorization": f"Bearer {token_l3}"},
        )
        assert res_decision.status_code == 200
        decision_data = res_decision.json()
        assert decision_data["status"] == "APPROVED" or decision_data["status"] == "APPROVED_AND_EXECUTED"
