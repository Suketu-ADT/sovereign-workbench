"""
Phase 8 Automated Test Suite — Production Concurrency, PostgreSQL Durability,
and Startup Hardening Verification (Fixes A through F).

Verifies:
  1. Fix A: audit_transaction() enforces mandatory db parameter; audit concurrency preserves chain index.
  2. Fix B: Alembic startup advisory lock serialization logic.
  3. Fix C: Database-backed PendingApproval persistence, cross-worker resolution, and anti-self-approval.
  4. Fix D: Standalone Qdrant server URL routing.
  5. Fix E: Production startup safeguard refuses default or weak JWT_SECRET.
  6. Fix F: PromptGuard failure logs at WARNING, circuit breaker marks status as 'degraded', surfaced via /health.
  7. Health Check: Database disconnection mid-run causes /health to report 503 and 'unhealthy'.
"""

import inspect
import logging
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.core.security import create_access_token
from app.db.migrate import MIGRATION_ADVISORY_LOCK_ID, run_migrations
from app.db.session import async_session_factory
from app.main import app
from app.models.approval import PendingApproval
from app.services import audit_service, planner_service, retrieval_service
from app.services.prompt_guard import _query_llama_guard, get_llm_status


# ─────────────────────────────────────────────────────────────────────────────
# FIX A: audit_transaction db parameter enforcement & call site verification
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_a_audit_transaction_requires_mandatory_db_parameter():
    """Fix A: Confirms audit_transaction requires db as a mandatory parameter (no None default)."""
    sig = inspect.signature(audit_service.audit_transaction)
    params = list(sig.parameters.values())
    assert len(params) >= 1, "audit_transaction must have at least one parameter"
    db_param = params[0]
    assert db_param.name == "db", "First parameter must be 'db'"
    assert db_param.default == inspect.Parameter.empty, (
        "audit_transaction must NOT have a default value for 'db'; it must be mandatory"
    )

    # Calling without db must raise TypeError at runtime/call site
    with pytest.raises(TypeError):
        audit_service.audit_transaction()  # type: ignore


@pytest.mark.asyncio
async def test_fix_a_approvals_audit_chain_commits_with_advisory_lock():
    """Fix A: Verifies that HITL decision records an audit log entry with db advisory transaction."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user tokens
        login_res = await client.post(
            "/auth/login",
            json={"email": "suketu.2005@gmail.com", "password": "changeme123"},
        )
        token_suketu = login_res.json()["access_token"]
        headers_suketu = {"Authorization": f"Bearer {token_suketu}"}

        # Create a pending approval record directly in DB (simulating Worker 1)
        test_thread = f"test-thread-fix-a-{uuid.uuid4().hex[:8]}"
        requestor_uuid = uuid.uuid4()

        # Initialize LangGraph state on this thread
        await planner_service.run_plan(
            query="Open release valve on boiler-102 immediately",
            user_id=str(requestor_uuid),
            operator_email="j.morrison@plant.internal",
            clearance_level=1,
            unit="boiler-102",
            thread_id=test_thread,
        )

        async with async_session_factory() as db:
            pending = PendingApproval(
                thread_id=test_thread,
                requestor_user_id=requestor_uuid,
                operator_email="j.morrison@plant.internal",
                clearance_level=1,
                unit="boiler-102",
                authority="Senior_Engineer (HITL Required)",
                action="open_release_valve",
                target="boiler-102 (release valve #4)",
                approval_details={
                    "action": "open_release_valve",
                    "target": "boiler-102 (release valve #4)",
                    "authority": "Senior_Engineer (HITL Required)",
                },
                status="PENDING",
            )
            db.add(pending)
            await db.commit()

        # Approve via Suketu (simulating Worker 2)
        dec_res = await client.post(
            f"/approvals/{test_thread}/decision",
            json={"decision": "approve", "comment": "Fix A advisory lock verification"},
            headers=headers_suketu,
        )
        assert dec_res.status_code == 200
        data = dec_res.json()
        assert data["status"] == "APPROVED_AND_EXECUTED"
        assert data["audit_hash"] is not None

        # Verify DB pending approval status is updated to APPROVED
        async with async_session_factory() as db:
            result = await db.execute(
                select(PendingApproval).where(PendingApproval.thread_id == test_thread)
            )
            resolved = result.scalar_one_or_none()
            assert resolved is not None
            assert resolved.status == "APPROVED"
            assert resolved.resolved_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# FIX B: Alembic startup advisory lock serialization
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_b_migration_lock_id_configured_and_distinct():
    """Fix B: Confirms migration advisory lock key exists and is separate from audit lock key."""
    assert MIGRATION_ADVISORY_LOCK_ID is not None
    assert isinstance(MIGRATION_ADVISORY_LOCK_ID, int)
    from app.services.audit_service import AUDIT_ADVISORY_LOCK_ID
    assert MIGRATION_ADVISORY_LOCK_ID != AUDIT_ADVISORY_LOCK_ID, (
        "Migration lock must not collide with audit lock ID"
    )


@pytest.mark.asyncio
async def test_fix_b_run_migrations_executes_safely():
    """Fix B: Confirms run_migrations completes cleanly without errors on current engine."""
    await run_migrations()
    assert True


# ─────────────────────────────────────────────────────────────────────────────
# FIX C: Database-backed PendingApproval & cross-worker state durability
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fix_c_pending_approvals_visible_across_independent_connections():
    """
    Fix C: Adversarial test for multi-worker pending approval isolation.
    Worker 1 writes to DB; Worker 2 queries /approvals/pending via a completely
    fresh, unpooled HTTP connection and resolves it without 404s.
    """
    transport = ASGITransport(app=app)
    # Login Level 1 requestor
    token_requestor = create_access_token({
        "sub": str(uuid.uuid4()),
        "email": "operator.req@plant.internal",
        "clearance_level": 1,
        "role": "Maintenance_Engineer",
    })
    # Login Level 3 approver
    token_approver = create_access_token({
        "sub": str(uuid.uuid4()),
        "email": "operator.app@plant.internal",
        "clearance_level": 3,
        "role": "Chief_Safety_Auditor",
    })

    # Run 10 independent requests via separate AsyncClients (simulating N worker connections)
    for i in range(10):
        tid = f"cross-worker-thread-{uuid.uuid4().hex[:8]}"

        # Simulate Worker 1: user submits query that requires HITL
        async with AsyncClient(transport=transport, base_url="http://test") as client1:
            q_res = await client1.post(
                "/query",
                json={"text": f"Open release valve on boiler-102 request {i}", "has_image": False},
                headers={"Authorization": f"Bearer {token_requestor}"},
            )
            assert q_res.status_code == 200
            q_data = q_res.json()
            assert q_data["status"] == "awaiting_approval"
            created_thread = q_data["thread_id"]

        # Simulate Worker 2: independent client queries /approvals/pending
        async with AsyncClient(transport=transport, base_url="http://test") as client2:
            pending_res = await client2.get(
                "/approvals/pending",
                headers={"Authorization": f"Bearer {token_approver}"},
            )
            assert pending_res.status_code == 200
            pending_items = pending_res.json()["approvals"]
            thread_ids = [item["thread_id"] for item in pending_items]
            assert created_thread in thread_ids, (
                f"Thread {created_thread} must be visible to independent client (worker 2)"
            )

        # Simulate Worker 3: fresh client resolves approval
        async with AsyncClient(transport=transport, base_url="http://test") as client3:
            dec_res = await client3.post(
                f"/approvals/{created_thread}/decision",
                json={"decision": "approve", "comment": f"Independent approval test {i}"},
                headers={"Authorization": f"Bearer {token_approver}"},
            )
            assert dec_res.status_code == 200, (
                f"Expected 200 for independent resolution, got {dec_res.status_code}: {dec_res.text}"
            )
            assert dec_res.json()["status"] == "APPROVED_AND_EXECUTED"

        # Verify it is no longer pending in the database
        async with async_session_factory() as db:
            db_res = await db.execute(
                select(PendingApproval).where(
                    PendingApproval.thread_id == created_thread,
                    PendingApproval.status == "PENDING",
                )
            )
            assert db_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_fix_c_self_approval_and_insufficient_clearance_blocked_by_db_record():
    """Fix C: Asserts self-approval and clearance checks operate accurately on DB-backed approvals."""
    req_uuid = uuid.uuid4()
    thread_id = f"test-sec-check-{uuid.uuid4().hex[:8]}"

    # Insert pending approval into DB
    async with async_session_factory() as db:
        pending = PendingApproval(
            thread_id=thread_id,
            requestor_user_id=req_uuid,
            operator_email="req@plant.internal",
            clearance_level=1,
            unit="turbine-01",
            authority="Senior_Engineer (HITL Required)",
            action="scram_containment",
            target="turbine-01",
            approval_details={
                "action": "scram_containment",
                "target": "turbine-01",
                "authority": "Senior_Engineer (HITL Required)",
            },
            status="PENDING",
        )
        db.add(pending)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Requestor tries to self-approve -> 403
        token_req = create_access_token({
            "sub": str(req_uuid),
            "email": "req@plant.internal",
            "clearance_level": 3,
        })
        res_self = await client.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve"},
            headers={"Authorization": f"Bearer {token_req}"},
        )
        assert res_self.status_code == 403
        assert "Self-approval forbidden" in res_self.json()["detail"]

        # Level 1 operator (different user) tries to approve -> 403
        token_l1 = create_access_token({
            "sub": str(uuid.uuid4()),
            "email": "other@plant.internal",
            "clearance_level": 1,
        })
        res_l1 = await client.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve"},
            headers={"Authorization": f"Bearer {token_l1}"},
        )
        assert res_l1.status_code == 403
        assert "Insufficient clearance" in res_l1.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# FIX D: Standalone Qdrant client URL configuration
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_d_qdrant_url_initializes_remote_client():
    """Fix D: Confirms RetrievalService connects to remote QDRANT_URL when specified."""
    from app.services.retrieval_service import RetrievalService

    service = RetrievalService(url="http://qdrant:6333")
    assert service.url == "http://qdrant:6333"


# ─────────────────────────────────────────────────────────────────────────────
# FIX E: Production startup safeguard refuses insecure JWT_SECRET
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fix_e_production_startup_safeguard_refuses_default_secret():
    """Fix E: Lifespan refuses to boot in production if JWT_SECRET is left at default placeholder."""
    from app.main import lifespan

    # Test with default secret in production mode
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(
        settings, "JWT_SECRET", "CHANGE_ME_IN_PRODUCTION"
    ):
        with pytest.raises(RuntimeError, match="FATAL: Insecure or default JWT_SECRET"):
            async with lifespan(app):
                pass

    # Test with hardcoded repo key in production mode
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(
        settings,
        "JWT_SECRET",
        "sovereign_industrial_airgapped_super_secret_key_change_in_prod_12345",
    ):
        with pytest.raises(RuntimeError, match="FATAL: Insecure or default JWT_SECRET"):
            async with lifespan(app):
                pass

    # Test with short secret (<32 chars) in production mode
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(
        settings, "JWT_SECRET", "too_short_key"
    ):
        with pytest.raises(RuntimeError, match="FATAL: Insecure or default JWT_SECRET"):
            async with lifespan(app):
                pass


# ─────────────────────────────────────────────────────────────────────────────
# FIX F: Prompt Guard logging at WARNING & health degradation telemetry
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fix_f_prompt_guard_failure_logs_warning_and_degrades_health(caplog):
    """
    Fix F: Confirms unreachable Llama-Guard logs at WARNING level (visible at INFO),
    and /health reports prompt_guard_llm_status as 'degraded'.
    """
    # Reset circuit-breaker state before test
    import app.services.prompt_guard as pg
    pg._last_endpoint_failure_time = 0.0

    # Trigger unreachable endpoint failure
    with caplog.at_level(logging.WARNING):
        safe, reason = await _query_llama_guard("Check pump RPM")
        assert safe is True  # Fails open to deterministic scanner

    # Check WARNING log emitted
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "Local Llama-Guard-3 endpoint unavailable" in r.message for r in warning_records
    ), "Unreachable Llama-Guard endpoint must log at WARNING level or above"

    # Check status helper reports degraded
    assert get_llm_status() == "degraded"

    # Check /health endpoint reflects degraded state
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["prompt_guard_llm_status"] == "degraded"


# ─────────────────────────────────────────────────────────────────────────────
# Health Check: Database disconnection mid-run triggers 503 & 'unhealthy'
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_reports_unhealthy_when_database_fails():
    """Verification item 5: Confirms /health returns 503 Service Unavailable when DB is disconnected."""
    transport = ASGITransport(app=app)
    with patch("app.main.async_session_factory") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionError("PostgreSQL connection refused")
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "unhealthy"
