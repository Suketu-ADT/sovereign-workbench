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


@pytest.mark.asyncio
async def test_vision_service_outcomes_tri_state():
    """
    Verifies that VisionService distinguishes three explicit outcomes:
      (a) No image provided -> status='skipped', reading=None
      (b) Corrupted/invalid/oversized image -> status='invalid_image', reading=None, error set
      (c) Genuine decode -> status='success', reading=float
    """
    import base64

    # Outcome (a): No image
    res_none = await vision_service.extract_gauge_reading(image_data=None)
    assert res_none.status == "skipped"
    assert res_none.reading is None
    assert res_none.error is None

    res_empty_str = await vision_service.extract_gauge_reading(image_data="   ")
    assert res_empty_str.status == "skipped"
    assert res_empty_str.reading is None

    # Outcome (b): Invalid magic bytes
    bad_bytes_b64 = base64.b64encode(b"NOT_A_VALID_IMAGE_HEADER_1234567890").decode("utf-8")
    res_bad = await vision_service.extract_gauge_reading(image_data=bad_bytes_b64)
    assert res_bad.status == "invalid_image"
    assert res_bad.reading is None
    assert res_bad.error is not None
    assert "rejected" in res_bad.assessment.lower()

    # Outcome (b): Oversized payload (>5MB)
    huge_payload = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 100)).decode("utf-8")
    res_huge = await vision_service.extract_gauge_reading(image_data=huge_payload)
    assert res_huge.status == "invalid_image"
    assert res_huge.reading is None
    assert res_huge.error is not None

    # Outcome (c): Valid image
    gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)
    res_good = await vision_service.extract_gauge_reading(image_data=gauge_b64)
    assert res_good.status == "success"
    assert res_good.reading is not None
    assert abs(res_good.reading - 6.4) <= 0.2
    assert res_good.error is None


@pytest.mark.asyncio
async def test_query_pipeline_with_corrupted_image_no_fake_reading():
    """
    Asserts that POST /query with has_image=True and corrupted bytes:
    1. Returns vision_analysis with status='invalid_image' and reading=None (never fake 6.4 bar).
    2. Does NOT execute or fabricate differential pressure calculation (calc_result is None).
    3. Logs visual asset rejection in audit log and zero fake CALCULATION_RESULT entries.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/auth/login",
            json={"email": "j.morrison@plant.internal", "password": "changeme123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get head index before query
        pre_audit = await client.get("/audit?limit=1", headers=headers)
        latest_idx_before = pre_audit.json()["entries"][0]["index"] if pre_audit.json()["entries"] else -1

        # Send garbage image data
        res = await client.post(
            "/query",
            json={
                "text": "Read gauge photo on boiler-102 and calculate pressure drop",
                "has_image": True,
                "image_data": "Tk9UX0FfUkVBTF9JTUFHRV9IRUFERVI=",
            },
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()

        # Must explicitly flag rejection without fabricating reading
        assert data["vision_analysis"] is not None
        assert data["vision_analysis"]["status"] == "invalid_image"
        assert data["vision_analysis"]["reading"] is None
        assert data["vision_analysis"]["error"] is not None

        # Must NOT fabricate calculation result from hallucinated reading
        assert data["calculation_result"] is None

        # Verify audit ledger
        audit_res = await client.get("/audit?limit=10", headers=headers)
        assert audit_res.status_code == 200
        entries = audit_res.json()["entries"]

        new_entries = [e for e in entries if e["index"] > latest_idx_before]
        vis_entries = [e for e in new_entries if e["event"] == "VISION_EXTRACTION"]
        assert len(vis_entries) > 0
        assert "rejected" in vis_entries[0]["detail"].lower()

        calc_entries = [e for e in new_entries if e["event"] == "CALCULATION_RESULT"]
        # No calculation entry should have been recorded for this request
        assert len(calc_entries) == 0
