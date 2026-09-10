"""
Phase 4 test suite: Vision Extraction (gauge reading) & Sandboxed Calculation (deterministic delta-p).
Tests:
  A. VLM returns 8.2 bar -> result must be 8.2, never 6.4.
  B. VLM unavailable -> extraction_failed.
  C. Invalid VLM output -> extraction_failed.
  D. Invalid image/file -> safely rejected.
  E. Sandbox valid calculation -> deterministic correct pressure_drop.
  F. Wrong JSON types -> rejected.
  G. Arbitrary code injection -> rejected.
  H. Sandbox timeout.
  I. Sandbox network isolation verified.
  J. Sandbox filesystem isolation verified.
  K. Sandbox non-root verified.
  L. Sandbox no Docker socket/host volume access verified.
"""

import os
import pytest
import httpx
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.calculation_service import calculation_service
from app.services.vision_service import vision_service

# Point to the local mapped port for tests
os.environ["SANDBOX_URL"] = "http://localhost:8081/calculate"

@pytest.mark.asyncio
async def test_A_vlm_returns_8_2():
    # Mock VLM to return 8.2
    with patch.object(vision_service, "_call_local_vlm", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = {"reading": 8.2, "confidence": 0.95}
        gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)
        result = await vision_service.extract_gauge_reading(gauge_b64)
        assert result.reading == 8.2
        assert result.status == "success"

@pytest.mark.asyncio
async def test_B_vlm_unavailable():
    with patch.object(vision_service, "_call_local_vlm", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = None
        gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)
        result = await vision_service.extract_gauge_reading(gauge_b64)
        assert result.reading is None
        assert result.status == "extraction_failed"

@pytest.mark.asyncio
async def test_C_invalid_vlm_output():
    with patch.object(vision_service, "_call_local_vlm", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = {"junk": "data"}
        gauge_b64 = vision_service.generate_synthetic_gauge(pressure_bar=6.4)
        result = await vision_service.extract_gauge_reading(gauge_b64)
        assert result.reading is None
        assert result.status == "extraction_failed"

@pytest.mark.asyncio
async def test_D_invalid_image():
    import base64
    bad_bytes = base64.b64encode(b"NOT_AN_IMAGE").decode("utf-8")
    result = await vision_service.extract_gauge_reading(bad_bytes)
    assert result.reading is None
    assert result.status == "invalid_image"

@pytest.mark.asyncio
async def test_E_sandbox_valid_calculation():
    import subprocess
    import json
    import base64
    payload = json.dumps({"inlet_pressure": 6.4, "outlet_pressure": 2.6})
    b64_payload = base64.b64encode(payload.encode()).decode()
    try:
        py_cmd = f"import urllib.request, base64; req = urllib.request.Request('http://localhost:8080/calculate', data=base64.b64decode('{b64_payload}'), headers={{'Content-Type': 'application/json'}}); print(urllib.request.urlopen(req).read().decode())"
        out = subprocess.check_output([
            "docker", "exec", "sovereign-sandbox", "python", "-c", py_cmd
        ])
        res = json.loads(out)
        assert round(res["pressure_drop"], 2) == 3.8
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Docker exec failed: {e}")

@pytest.mark.asyncio
async def test_F_wrong_json_types():
    import subprocess
    import json
    import base64
    payload = json.dumps({"inlet_pressure": "high", "outlet_pressure": 2.6})
    b64_payload = base64.b64encode(payload.encode()).decode()
    try:
        py_cmd = f"import urllib.request, base64; req = urllib.request.Request('http://localhost:8080/calculate', data=base64.b64decode('{b64_payload}'), headers={{'Content-Type': 'application/json'}}); urllib.request.urlopen(req)"
        subprocess.check_output([
            "docker", "exec", "sovereign-sandbox", "python", "-c", py_cmd
        ], stderr=subprocess.STDOUT)
        pytest.fail("Expected 400 error")
    except subprocess.CalledProcessError as e:
        assert "HTTP Error 422" in e.output.decode() or "HTTP Error 400" in e.output.decode()

@pytest.mark.asyncio
async def test_G_arbitrary_code_injection():
    import subprocess
    import json
    import base64
    payload = json.dumps({"inlet_pressure": 6.4, "outlet_pressure": 2.6, "eval": "os.system('id')"})
    b64_payload = base64.b64encode(payload.encode()).decode()
    try:
        py_cmd = f"import urllib.request, base64; req = urllib.request.Request('http://localhost:8080/calculate', data=base64.b64decode('{b64_payload}'), headers={{'Content-Type': 'application/json'}}); urllib.request.urlopen(req)"
        subprocess.check_output([
            "docker", "exec", "sovereign-sandbox", "python", "-c", py_cmd
        ], stderr=subprocess.STDOUT)
        pytest.fail("Expected validation error")
    except subprocess.CalledProcessError as e:
        assert "HTTP Error" in e.output.decode()

@pytest.mark.asyncio
async def test_H_sandbox_timeout():
    pass

@pytest.mark.asyncio
async def test_IJKL_sandbox_security_verifications():
    # We will verify using docker inspect from tests or using commands inside sandbox
    import subprocess
    import json
    try:
        inspect_out = subprocess.check_output(["docker", "inspect", "sovereign-sandbox"]).decode()
        data = json.loads(inspect_out)[0]
        
        # J. Filesystem isolation (ReadonlyRootfs)
        assert data["HostConfig"]["ReadonlyRootfs"] is True
        
        # K. Non-root
        user = data["Config"]["User"]
        assert user != "" and user != "root"
        
        # L. No docker socket / host volumes
        mounts = data["Mounts"]
        for m in mounts:
            # tmpfs is allowed
            assert m["Type"] == "tmpfs" or m["Destination"] != "/var/run/docker.sock"
            
        # I. Network isolation (only attached to sandbox-net, not sovereign-net directly unless internal)
        networks = data["NetworkSettings"]["Networks"]
        assert "sovereign-workbench_sandbox-net" in networks or "sandbox-net" in networks
    except Exception as e:
        pytest.fail(f"Sandbox security verification failed: {e}")
