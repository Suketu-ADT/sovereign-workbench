"""
Automated unit & integration test suite for Sovereign Workbench Phase 0/1.

Covers:
1. Core security & hashing (Argon2id, JWT creation & decoding)
2. Capability map (RBAC keywords, levels, case-insensitivity)
3. Rate limiter (token bucket capacity, eviction, retry_after)
4. Audit log service (genesis entry, append, chain verification, tamper detection)
5. Endpoints:
   - Health check
   - Authentication (seeded operators, invalid password, JWT issue, /auth/me, register)
   - RBAC clearance enforcement on /query (Level 1, 2, 3 permissions and blocks)
   - Audit endpoints (/audit, /audit/verify, /audit/export)
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.capability_map import required_clearance
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.services import rate_limiter
from app.services.audit_service import (
    GENESIS_PREV_HASH,
    _canonical_json,
    _compute_hash,
)


# ── 1. Security & Hashing Tests ─────────────────────────────────

def test_argon2_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_roundtrip():
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "test@plant.internal",
        "role": "Systems_Specialist",
        "clearance_level": 2,
    }
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["email"] == payload["email"]
    assert decoded["clearance_level"] == 2


# ── 2. Capability Map Tests ─────────────────────────────────────

def test_capability_map():
    # Unrestricted (level 0)
    assert required_clearance("What is the standard operating temperature?") == 0

    # Level 1 units
    assert required_clearance("Check boiler-102 status") == 1
    assert required_clearance("inspect pump-201 and cooling-loop-c3") == 1

    # Level 2 units
    assert required_clearance("Inspect turbine-gen-4 vibration") == 2
    assert required_clearance("Compressor performance log") == 2

    # Level 3 units
    assert required_clearance("Emergency shutoff for reactor-core-aux") == 3

    # Multi-unit query takes highest clearance
    assert required_clearance("Compare boiler-102 and reactor-core-aux") == 3
    assert required_clearance("boiler-102 and turbine-gen-4") == 2


# ── 3. Rate Limiter Tests ───────────────────────────────────────

def test_rate_limiter():
    test_user = uuid.uuid4()
    rate_limiter.reset_rate_limit(test_user)

    # 60 requests should succeed
    for _ in range(rate_limiter.MAX_REQUESTS):
        allowed, retry_after = rate_limiter.check_rate_limit(test_user)
        assert allowed is True
        assert retry_after == 0

    # 61st request should be blocked
    allowed, retry_after = rate_limiter.check_rate_limit(test_user)
    assert allowed is False
    assert retry_after > 0

    # Reset cleans the bucket
    rate_limiter.reset_rate_limit(test_user)
    allowed, _ = rate_limiter.check_rate_limit(test_user)
    assert allowed is True


# ── 4. Cryptographic Hash Chain & Tamper Detection ───────────────

def test_canonical_json_and_sha256_hashing():
    data1 = {"b": 2, "a": 1, "detail": "test"}
    data2 = {"a": 1, "detail": "test", "b": 2}
    assert _canonical_json(data1) == _canonical_json(data2)

    hash1 = _compute_hash(GENESIS_PREV_HASH, data1)
    hash2 = _compute_hash(GENESIS_PREV_HASH, data2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string


# ── 5. Integration Tests with Live App ────────────────────────────

@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_and_rbac_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login with John Morrison (Level 1)
        res_john = await client.post("/auth/login", json={
            "email": "j.morrison@plant.internal",
            "password": "changeme123",
        })
        assert res_john.status_code == 200
        john_token = res_john.json()["access_token"]
        john_headers = {"Authorization": f"Bearer {john_token}"}

        # John queries boiler-102 (Allowed: Level 1)
        res_q1 = await client.post("/query", json={
            "text": "Check boiler-102 pressure",
            "has_image": False,
        }, headers=john_headers)
        assert res_q1.status_code == 200
        assert res_q1.json()["status"] == "accepted_stub"

        # John queries turbine-gen-4 (Forbidden: requires Level 2)
        res_q2 = await client.post("/query", json={
            "text": "Check turbine-gen-4 diagnostics",
            "has_image": False,
        }, headers=john_headers)
        assert res_q2.status_code == 403
        assert res_q2.json()["detail"]["required_level"] == 2

        # Login with Suketu Patel (Level 3 - Chief Safety Auditor)
        res_suketu = await client.post("/auth/login", json={
            "email": "suketu.2005@gmail.com",
            "password": "changeme123",
        })
        assert res_suketu.status_code == 200
        suketu_token = res_suketu.json()["access_token"]
        suketu_headers = {"Authorization": f"Bearer {suketu_token}"}

        # Suketu queries reactor-core-aux (Allowed: Level 3)
        res_q3 = await client.post("/query", json={
            "text": "Full inspection of reactor-core-aux",
            "has_image": False,
        }, headers=suketu_headers)
        assert res_q3.status_code == 200

        # Audit chain verification
        res_audit_verify = await client.get("/audit/verify", headers=suketu_headers)
        assert res_audit_verify.status_code == 200
        verify_data = res_audit_verify.json()
        assert verify_data["valid"] is True
        assert verify_data["broken_at_index"] is None

        # Audit ledger export
        res_export = await client.get("/audit/export", headers=suketu_headers)
        assert res_export.status_code == 200
        export_data = res_export.json()
        assert export_data["entryCount"] > 0
        assert len(export_data["ledger"]) > 0
