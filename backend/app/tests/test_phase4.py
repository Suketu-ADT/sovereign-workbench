"""
Phase 4 test suite: Vision Extraction (gauge reading) & Sandboxed Calculation (deterministic delta-p).
Tests:
  1. Synthetic gauge image generation and OpenCV needle angle extraction
  2. Sandboxed arithmetic evaluation and anomaly detection (normal vs abnormal delta-p)
  3. Sandbox security AST enforcement (blocks malicious code / non-arithmetic syntax)
  4. Full pipeline integration: POST /query with gauge photo executes Vision + Calculation
  5. Audit log commitment: VISION_EXTRACTION and CALCULATION_RESULT committed to hash-chain
  6. Cryptographic audit verification of vision and calculation events
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.calculation_service import calculation_service
from app.services.vision_service import vision_service


@pytest.mark.asyncio
async def test_synthetic_gauge_opencv_extraction():
    """Verify that synthetic pressure gauge images are parsed accurately by OpenCV."""
    gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)
    assert gauge_b64.startswith("data:image/png;base64,")

    result = await vision_service.extract_gauge_reading(gauge_b64, equipment_unit="boiler-102")
    assert abs(result.reading - 6.4) <= 0.2
    assert result.unit == "bar"
    assert result.parameter == "inlet_pressure"
    assert result.confidence >= 0.90
    assert "Within normal range" in result.assessment


def test_sandboxed_calculation_normal():
    """Verify normal pressure drop calculation (2.0 <= delta-p <= 5.0)."""
    res = calculation_service.compute_differential_pressure(
        inlet_pressure=6.4,
        outlet_pressure=2.6,
        normal_min=2.0,
        normal_max=5.0,
    )
    assert res.pressure_drop == 3.8
    assert res.status == "NORMAL"
    assert res.is_abnormal is False
    assert res.recommended_action is None


def test_sandboxed_calculation_abnormal_high():
    """Verify high pressure drop triggers ABNORMAL status and recommends valve opening."""
    res = calculation_service.compute_differential_pressure(
        inlet_pressure=8.5,
        outlet_pressure=2.6,
        normal_min=2.0,
        normal_max=5.0,
    )
    assert res.pressure_drop == 5.9
    assert res.status == "ABNORMAL"
    assert res.is_abnormal is True
    assert res.recommended_action == "open_release_valve"


def test_sandboxed_calculation_security():
    """Verify mathematical sandbox rejects non-arithmetic code, imports, and function calls."""
    with pytest.raises(ValueError):
        calculation_service.evaluate_sandboxed("__import__('os').system('echo pwned')", {})

    with pytest.raises(ValueError):
        calculation_service.evaluate_sandboxed("[x for x in (1, 2, 3)]", {})

    with pytest.raises(ValueError):
        calculation_service.evaluate_sandboxed("open('sovereign.db')", {})


@pytest.mark.asyncio
async def test_query_pipeline_vision_and_calculation_integration():
    """
    Test full defense pipeline with seed query:
    'Fetch boiler-102 log, read gauge photo, calculate pressure drop, open release valve if abnormal.'
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login John Morrison (Level 1)
        login_res = await client.post(
            "/auth/login",
            json={"email": "j.morrison@plant.internal", "password": "changeme123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Generate gauge photo
        gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)

        # Submit query with gauge image
        query_text = "Fetch boiler-102 log, read gauge photo, calculate pressure drop, open release valve if abnormal."
        res = await client.post(
            "/query",
            json={
                "text": query_text,
                "has_image": True,
                "image_data": gauge_b64,
            },
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()

        # 1. Check retrieval
        assert len(data["retrieved_chunks"]) > 0
        assert all(c["min_clearance"] <= 1 for c in data["retrieved_chunks"])

        # 2. Check vision analysis
        assert data["vision_analysis"] is not None
        vis = data["vision_analysis"]
        assert abs(vis["reading"] - 6.4) <= 0.2
        assert vis["unit"] == "bar"
        assert vis["confidence"] >= 0.90

        # 3. Check calculation result
        assert data["calculation_result"] is not None
        calc = data["calculation_result"]
        assert abs(calc["pressure_drop"] - 3.8) <= 0.2
        assert calc["status"] == "NORMAL"
        assert calc["is_abnormal"] is False

        # 4. Verify audit ledger contains VISION_EXTRACTION and CALCULATION_RESULT
        audit_res = await client.get("/audit?limit=25", headers=headers)
        assert audit_res.status_code == 200
        entries = audit_res.json()["entries"]

        vis_entries = [e for e in entries if e["event"] == "VISION_EXTRACTION"]
        calc_entries = [e for e in entries if e["event"] == "CALCULATION_RESULT"]

        assert len(vis_entries) > 0
        assert len(calc_entries) > 0
        assert "bar" in vis_entries[0]["detail"]
        assert "evaluated to" in calc_entries[0]["detail"]

        # 5. Verify cryptographic hash chain integrity
        verify_res = await client.get("/audit/verify", headers=headers)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["valid"] is True
        assert verify_data["broken_at_index"] is None
        assert verify_data["entries_checked"] > 0
