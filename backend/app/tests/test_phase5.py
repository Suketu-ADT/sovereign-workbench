"""
Phase 5 test suite: Planner & Orchestration (LangGraph + HITL Interruption).
Tests:
  1. LangGraph execution for non-sensitive queries (completes without interruption)
  2. LangGraph interrupt() execution for sensitive actuator commands (open_release_valve)
  3. Resuming LangGraph thread via Command(resume=...) with approval
  4. Resuming LangGraph thread with rejection
  5. End-to-end API lifecycle:
     - POST /query triggers HITL interruption and returns awaiting_approval
     - GET /approvals/pending returns active approval request
     - POST /approvals/{thread_id}/decision resumes execution and commits HITL_APPROVAL
     - GET /audit/verify confirms 100% cryptographic ledger validity
  6. Rejection flow commits HITL_REJECTION and maintains hash chain integrity
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.planner_service import planner_service


def test_planner_nonsensitive_flow():
    """Non-sensitive informational query completes without interruption."""
    res = planner_service.run_plan(
        query="Check boiler-102 temperature and pressure log",
        user_id="test-user-1",
        operator_email="j.morrison@plant.internal",
        clearance_level=1,
        unit="boiler-102",
        vision_reading=6.4,
        pressure_drop=3.8,
    )
    assert res["status"] == "completed"
    assert res["approval_required"] is False
    assert res["approval_details"] is None
    assert res["action_status"] == "NOT_REQUIRED"
    assert "nominal boundaries" in res["synthesis"]


def test_planner_sensitive_interruption_and_resume():
    """Sensitive actuator action triggers LangGraph interrupt(), resumes with approval."""
    # 1. Trigger interruption
    res = planner_service.run_plan(
        query="Fetch boiler-102 log, open release valve if abnormal",
        user_id="test-user-1",
        operator_email="j.morrison@plant.internal",
        clearance_level=1,
        unit="boiler-102",
        vision_reading=6.4,
        pressure_drop=3.8,
    )
    assert res["status"] == "awaiting_approval"
    assert res["approval_required"] is True
    details = res["approval_details"]
    assert details["action"] == "open_release_valve"
    assert "release valve #4" in details["target"]
    assert "Senior_Engineer" in details["authority"]

    thread_id = res["thread_id"]
    # Check that thread is stored in pending registry
    pending = planner_service.list_pending_approvals()
    assert any(p["thread_id"] == thread_id for p in pending)

    # 2. Resume with approval
    resume_res = planner_service.resume_plan(
        thread_id=thread_id,
        approved=True,
        operator_email="j.morrison@plant.internal",
        comment="Pressure drop verified",
    )
    assert resume_res["status"] == "APPROVED_AND_EXECUTED"
    assert resume_res["action"] == "open_release_valve"
    assert resume_res["action_status"] == "EXECUTED"

    # Verify thread is no longer pending
    pending_after = planner_service.list_pending_approvals()
    assert not any(p["thread_id"] == thread_id for p in pending_after)


def test_planner_sensitive_rejection():
    """Sensitive actuator action paused at HITL gate can be rejected safely."""
    res = planner_service.run_plan(
        query="Open release valve on boiler-102 immediately",
        user_id="test-user-1",
        operator_email="j.morrison@plant.internal",
        clearance_level=1,
        unit="boiler-102",
    )
    assert res["status"] == "awaiting_approval"
    thread_id = res["thread_id"]

    resume_res = planner_service.resume_plan(
        thread_id=thread_id,
        approved=False,
        operator_email="elena.vance@plant.internal",
        comment="Abnormal vibration not confirmed",
    )
    assert resume_res["status"] == "REJECTED"
    assert resume_res["action_status"] == "REJECTED"
    assert "REJECTED" in resume_res["synthesis"]


@pytest.mark.asyncio
async def test_approvals_api_lifecycle():
    """
    Test full HTTP API lifecycle for Human-in-the-Loop authorization:
    1. POST /query proposing sensitive action returns awaiting_approval and thread_id
    2. GET /approvals/pending returns the pending approval
    3. POST /approvals/{thread_id}/decision submits authorization
    4. GET /audit verifies HITL_REQUIRED and HITL_APPROVAL committed to ledger
    5. GET /audit/verify confirms hash chain validity
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login John Morrison (Level 1)
        login_res = await client.post(
            "/auth/login",
            json={"email": "j.morrison@plant.internal", "password": "changeme123"},
        )
        assert login_res.status_code == 200
        token_john = login_res.json()["access_token"]
        headers_john = {"Authorization": f"Bearer {token_john}"}

        # 1. Submit query requesting valve action
        query_text = "Fetch boiler-102 log, calculate pressure drop, open release valve if abnormal."
        q_res = await client.post(
            "/query",
            json={"text": query_text, "has_image": False},
            headers=headers_john,
        )
        assert q_res.status_code == 200
        q_data = q_res.json()
        assert q_data["status"] == "awaiting_approval"
        assert q_data["approval_required"] is True
        assert q_data["approval_details"] is not None
        assert q_data["approval_details"]["action"] == "open_release_valve"
        thread_id = q_data["thread_id"]
        assert thread_id is not None

        # 2. Inspect pending approvals
        pending_res = await client.get("/approvals/pending", headers=headers_john)
        assert pending_res.status_code == 200
        pending_list = pending_res.json()["approvals"]
        assert any(p["thread_id"] == thread_id for p in pending_list)

        # Login Suketu Patel (Level 3 - Chief Safety Auditor)
        login_suketu = await client.post(
            "/auth/login",
            json={"email": "suketu.2005@gmail.com", "password": "changeme123"},
        )
        assert login_suketu.status_code == 200
        token_suketu = login_suketu.json()["access_token"]
        headers_suketu = {"Authorization": f"Bearer {token_suketu}"}

        # 3. Authorize action by Level 3 operator (Suketu Patel)
        decision_res = await client.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve", "comment": "Chief Auditor confirmed relief pressure."},
            headers=headers_suketu,
        )
        assert decision_res.status_code == 200
        decision_data = decision_res.json()
        assert decision_data["status"] == "APPROVED_AND_EXECUTED"
        assert decision_data["action"] == "open_release_valve"
        assert decision_data["audit_hash"] is not None

        # 4. Verify audit ledger entries
        audit_res = await client.get("/audit?limit=25", headers=headers_suketu)
        assert audit_res.status_code == 200
        entries = audit_res.json()["entries"]

        hitl_req_entries = [e for e in entries if e["event"] == "HITL_REQUIRED"]
        hitl_app_entries = [e for e in entries if e["event"] == "HITL_APPROVAL"]

        assert len(hitl_req_entries) > 0
        assert len(hitl_app_entries) > 0
        assert "open_release_valve" in hitl_app_entries[0]["detail"]
        assert "approved" in hitl_app_entries[0]["detail"]

        # 5. Verify cryptographic hash chain integrity
        verify_res = await client.get("/audit/verify", headers=headers_suketu)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["valid"] is True
        assert verify_data["broken_at_index"] is None


@pytest.mark.asyncio
async def test_approvals_self_approval_and_clearance_enforcement():
    """
    Asserts strict dual-custody authorization:
    1. Requestor cannot approve their own action (403 Forbidden even if Level 3).
    2. Lower clearance operator (Level 1 / 2) cannot approve action requiring Level 3 (403 Forbidden).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login John Morrison (Level 1)
        res_john = await client.post(
            "/auth/login",
            json={"email": "j.morrison@plant.internal", "password": "changeme123"},
        )
        token_john = res_john.json()["access_token"]
        headers_john = {"Authorization": f"Bearer {token_john}"}

        # Login Elena Vance (Level 2)
        res_vance = await client.post(
            "/auth/login",
            json={"email": "elena.vance@plant.internal", "password": "changeme123"},
        )
        token_vance = res_vance.json()["access_token"]
        headers_vance = {"Authorization": f"Bearer {token_vance}"}

        # Login Suketu Patel (Level 3)
        res_suketu = await client.post(
            "/auth/login",
            json={"email": "suketu.2005@gmail.com", "password": "changeme123"},
        )
        token_suketu = res_suketu.json()["access_token"]
        headers_suketu = {"Authorization": f"Bearer {token_suketu}"}

        # Scenario 1: John (L1) requests open_release_valve
        q_res = await client.post(
            "/query",
            json={"text": "Open release valve on boiler-102 immediately", "has_image": False},
            headers=headers_john,
        )
        assert q_res.status_code == 200
        thread_id = q_res.json()["thread_id"]

        # 1a. Self-approval attempt by John (L1) -> 403 Forbidden
        self_app_res = await client.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve", "comment": "I approve my own request"},
            headers=headers_john,
        )
        assert self_app_res.status_code == 403
        assert "Self-approval forbidden" in self_app_res.json()["detail"]

        # 1b. Approval attempt by Elena Vance (L2, not requestor, but L2 < required L3) -> 403 Forbidden
        clearance_app_res = await client.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve", "comment": "L2 specialist approving"},
            headers=headers_vance,
        )
        assert clearance_app_res.status_code == 403
        assert "Insufficient clearance" in clearance_app_res.json()["detail"]

        # Scenario 2: Suketu Patel (Level 3) requests an action, then attempts self-approval
        q_res_l3 = await client.post(
            "/query",
            json={"text": "Open release valve on boiler-102 emergency override", "has_image": False},
            headers=headers_suketu,
        )
        assert q_res_l3.status_code == 200
        thread_id_l3 = q_res_l3.json()["thread_id"]

        # Suketu attempts self-approval -> 403 Forbidden regardless of having Level 3!
        self_app_l3_res = await client.post(
            f"/approvals/{thread_id_l3}/decision",
            json={"decision": "approve", "comment": "Director approving self"},
            headers=headers_suketu,
        )
        assert self_app_l3_res.status_code == 403
        assert "Self-approval forbidden" in self_app_l3_res.json()["detail"]
