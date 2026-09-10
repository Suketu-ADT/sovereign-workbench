"""
Tests for Multimodal Visual Asset Understanding & Diagram Explanation.
Verifies that non-gauge diagrams (e.g. flowcharts, architectures, infographics)
are properly analyzed by the VLM rather than misrouted to boiler-102 dial gauge reading.
"""

import base64
import cv2
import numpy as np
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.security import create_access_token
from app.services.vision_service import vision_service
from app.api.query import is_gauge_query


def _make_test_image_b64() -> str:
    """Creates a simple valid test diagram image in base64."""
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    img[:] = (240, 240, 240)
    cv2.rectangle(img, (20, 20), (120, 80), (200, 50, 50), -1)
    cv2.putText(img, "STEP 1", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.rectangle(img, (180, 20), (280, 80), (50, 150, 50), -1)
    cv2.putText(img, "STEP 2", (190, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.arrowedLine(img, (125, 50), (175, 50), (0, 0, 0), 2)
    _, buf = cv2.imencode(".png", img)
    return "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")


def test_is_gauge_query_distinction():
    """Verifies that is_gauge_query accurately differentiates plant gauge queries from diagram explanations."""
    # Diagram / visual explanation queries
    assert is_gauge_query("explain the image") is False
    assert is_gauge_query("describe what is in this diagram") is False
    assert is_gauge_query("explain the 5 stages of the NLP pipeline") is False
    assert is_gauge_query("what does this flowchart represent?") is False
    assert is_gauge_query("summarize the architecture in this diagram") is False

    # Operational plant gauge telemetry queries
    assert is_gauge_query("read the pressure gauge on boiler-102") is True
    assert is_gauge_query("what is the inlet pressure dial reading?") is True
    assert is_gauge_query("The inlet reads high, should I vent the pressure?") is True
    assert is_gauge_query("calculate differential pressure from this gauge") is True


@pytest.mark.asyncio
async def test_analyze_visual_asset_returns_structured_breakdown():
    """Verifies analyze_visual_asset returns structured analysis."""
    test_img = _make_test_image_b64()

    with patch.object(vision_service, "_call_vlm_text", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = (
            "### Pipeline Diagram Analysis\n"
            "The image illustrates a 2-step process:\n"
            "- Step 1: Input Data Processing\n"
            "- Step 2: Model Inference"
        )
        res = await vision_service.analyze_visual_asset(test_img, prompt="explain the image")
        assert res["status"] == "success"
        assert "Pipeline Diagram Analysis" in res["explanation"]
        assert res["dimensions"]["width"] == 300
        assert res["dimensions"]["height"] == 200


@pytest.mark.asyncio
async def test_pipeline_streaming_multimodal_explanation():
    """
    Submits 'explain the image' with an attached diagram to /query/stream.
    Verifies that:
      1. Step 5 is Multimodal Visual Analysis.
      2. Step 6 calculation is skipped without error.
      3. Step 7 does NOT propose read_gauge on boiler-102.
      4. Complete event delivers the full multimodal breakdown.
    """
    test_img = _make_test_image_b64()
    token = create_access_token({
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "analyst@plant.internal",
        "clearance_level": 2,
        "role": "Engineer",
    })

    explanation_sample = (
        "### NLP Pipeline Architecture\n"
        "1. Data Acquisition\n"
        "2. Text Preprocessing\n"
        "3. Feature Engineering\n"
        "4. Modelling & Evaluation\n"
        "5. Deployment"
    )

    with patch.object(vision_service, "analyze_visual_asset", new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "status": "success",
            "explanation": explanation_sample,
            "dimensions": {"width": 300, "height": 200},
            "model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "provider": "local",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/query/stream",
                json={
                    "text": "explain the image",
                    "has_image": True,
                    "image_data": test_img,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            content = res.text

            # Verify events streamed
            assert "Multimodal Visual Analysis" in content
            assert "Qwen2.5-VL" in content
            assert "Calculation skipped" in content
            assert "Proposed action read_gauge does not require HITL" not in content
            assert "NLP Pipeline Architecture" in content
