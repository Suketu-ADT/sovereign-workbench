"""
Phase 7 E2E Tests: Boiler-102 Positive and Negative Path

These tests exercise the complete defense pipeline with mocked external
dependencies (LLM, vision model, Qdrant, Docker sandbox) while validating
real application components:
  - Authentication (JWT)
  - Prompt Guard interface
  - RBAC enforcement
  - Retrieval interface
  - Vision interface
  - Calculation sandbox interface (mocked at HTTP boundary)
  - LangGraph planner routing
  - Authorization / HITL interrupt
  - Approval / rejection
  - Audit chain
"""

import pytest
from httpx import ASGITransport, AsyncClient
import base64
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.core.security import create_access_token
from app.schemas.query import CalculationResult, RetrievedChunk, VisionResult


def _make_test_chunks():
    """Return a list of RetrievedChunk objects for Boiler-102 test scenarios."""
    return [
        RetrievedChunk(
            id="chunk-1",
            unit="boiler-102",
            sop_id="SOP-B102-001",
            title="Boiler-102 Nominal Pressure Parameters",
            content="Boiler-102 nominal pressure is 2.6 bar.",
            min_clearance=1,
            score=0.92,
        )
    ]


@pytest.mark.asyncio
@patch("app.services.prompt_guard.is_safe", new_callable=AsyncMock)
@patch("app.services.retrieval_service.retrieval_service.retrieve")
@patch("app.services.vision_service.vision_service.extract_gauge_reading", new_callable=AsyncMock)
@patch("app.services.calculation_service.calculation_service.compute_differential_pressure", new_callable=AsyncMock)
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_e2e_boiler_102_positive_path(
    mock_planner, mock_calc, mock_vision, mock_search, mock_guard
):
    """
    Positive E2E: L3 operator submits high-pressure query with gauge image.
    Pipeline: auth → guard → RBAC → retrieval → vision → calculation → planner
    → HITL interrupt → separate L3 approves → execution confirmed.

    Uses reading=8.2 bar (not the deprecated 6.4 fallback).
    """
    # Mock external dependencies for deterministic testing
    mock_guard.return_value = (True, "Safe")
    mock_search.return_value = _make_test_chunks()
    mock_vision.return_value = VisionResult(
        status="success",
        reading=8.2,
        unit="bar",
        parameter="inlet_pressure",
        confidence=0.95,
        assessment="High pressure advisory: 8.2 bar exceeds normal upper limit (7.0 bar)",
        error=None,
    )
    mock_calc.return_value = CalculationResult(
        formula="inlet_pressure - outlet_pressure",
        inlet_pressure=8.2,
        outlet_pressure=2.6,
        pressure_drop=5.6,
        unit="bar",
        normal_range="2.0 – 5.0 bar",
        status="ABNORMAL",
        is_abnormal=True,
        recommended_action="open_release_valve",
    )
    mock_planner.return_value = {
        "response": '{"intent": "vent pressure", "required_tools": ["open_release_valve"], "proposed_action": "open_release_valve", "requires_sensitive_approval": true, "reason": "High pressure detected at 8.2 bar"}'
    }

    transport = ASGITransport(app=app)

    # L3 operator (requestor)
    token_requestor = create_access_token({
        "sub": "22222222-2222-2222-2222-222222222222",
        "email": "e.vance@plant.internal",
        "clearance_level": 3,
        "role": "Plant_Director",
    })

    # Different L3 operator (approver — dual custody)
    token_approver = create_access_token({
        "sub": "44444444-4444-4444-4444-444444444444",
        "email": "admin@plant.internal",
        "clearance_level": 3,
        "role": "Chief_Safety_Auditor",
    })

    fake_b64 = base64.b64encode(b"FAKE_IMAGE_DATA_HEADER").decode("ascii")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Submit query through the pipeline
        res = await ac.post(
            "/query",
            json={
                "text": "The inlet reads high, should I vent the pressure?",
                "has_image": True,
                "image_data": fake_b64,
            },
            headers={"Authorization": f"Bearer {token_requestor}"},
        )
        assert res.status_code == 200
        data = res.json()

        # Validate pipeline produced awaiting_approval
        assert data["status"] == "awaiting_approval"
        assert data["approval_required"] is True
        assert data["approval_details"] is not None
        assert data["approval_details"]["action"] == "open_release_valve"
        thread_id = data["thread_id"]
        assert thread_id is not None

        # Validate vision reading was captured (8.2, not 6.4)
        assert data["vision_analysis"] is not None
        assert data["vision_analysis"]["reading"] == 8.2
        assert data["vision_analysis"]["assessment"] is not None

        # Validate calculation result (8.2 - 2.6 = 5.6)
        assert data["calculation_result"] is not None
        assert round(data["calculation_result"]["pressure_drop"], 2) == 5.6

        # Step 2: Approve with different L3 user (dual custody)
        approve_res = await ac.post(
            f"/approvals/{thread_id}/decision",
            json={"decision": "approve", "comment": "Confirmed high pressure, proceed with venting."},
            headers={"Authorization": f"Bearer {token_approver}"},
        )
        assert approve_res.status_code == 200
        app_data = approve_res.json()
        assert app_data["status"] == "APPROVED_AND_EXECUTED"
        assert app_data["action"] == "open_release_valve"
        assert app_data["audit_hash"] is not None


@pytest.mark.asyncio
@patch("app.services.prompt_guard.is_safe", new_callable=AsyncMock)
@patch("app.services.retrieval_service.retrieval_service.retrieve")
@patch("app.services.vision_service.vision_service.extract_gauge_reading", new_callable=AsyncMock)
@patch("app.services.calculation_service.calculation_service.compute_differential_pressure", new_callable=AsyncMock)
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_e2e_boiler_102_negative_path(
    mock_planner, mock_calc, mock_vision, mock_search, mock_guard
):
    """
    Negative E2E: L1 operator submits same high-pressure query.
    Pipeline: auth → guard → RBAC (query passes since boiler-102 is L1) → retrieval
    → vision → calculation → planner proposes open_release_valve
    → RBAC enforcement BLOCKS (open_release_valve requires L3, user has L1)
    → NO HITL → NO execution → accepted_stub with REJECTED_UNAUTHORIZED
    """
    mock_guard.return_value = (True, "Safe")
    mock_search.return_value = _make_test_chunks()
    mock_vision.return_value = VisionResult(
        status="success",
        reading=8.2,
        unit="bar",
        parameter="inlet_pressure",
        confidence=0.95,
        assessment="High pressure advisory: 8.2 bar exceeds normal upper limit (7.0 bar)",
        error=None,
    )
    mock_calc.return_value = CalculationResult(
        formula="inlet_pressure - outlet_pressure",
        inlet_pressure=8.2,
        outlet_pressure=2.6,
        pressure_drop=5.6,
        unit="bar",
        normal_range="2.0 – 5.0 bar",
        status="ABNORMAL",
        is_abnormal=True,
        recommended_action="open_release_valve",
    )
    mock_planner.return_value = {
        "response": '{"intent": "vent pressure", "required_tools": ["open_release_valve"], "proposed_action": "open_release_valve", "requires_sensitive_approval": true, "reason": "High pressure"}'
    }

    transport = ASGITransport(app=app)
    # L1 operator — insufficient clearance for open_release_valve (requires L3)
    token = create_access_token({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "engineer@plant.internal",
        "clearance_level": 1,
        "role": "Maintenance_Engineer",
    })

    fake_b64 = base64.b64encode(b"FAKE_IMAGE_DATA_HEADER").decode("ascii")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query",
            json={
                "text": "The inlet reads high, should I vent the pressure?",
                "has_image": True,
                "image_data": fake_b64,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()

        # Planner proposed open_release_valve but RBAC blocked it (L1 < L3 required)
        assert data["status"] == "accepted_stub"
        assert data["approval_required"] is False
        # No HITL was triggered — action was rejected before reaching the gate
        assert data.get("thread_id") is not None
        assert data["approval_details"] is None
