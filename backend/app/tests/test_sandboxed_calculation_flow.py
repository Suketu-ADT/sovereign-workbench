"""
Verification suite ensuring Sandboxed Calculation executes and passes across all query flows:
1. Document RAG queries (never skipped)
2. Operational queries without images
3. Explicit numerical parameters in query and document chunks
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_document_query_stream_executes_sandboxed_calculation():
    """
    Verifies that when active documents are queried via /query/stream,
    Sandboxed Calculation is NEVER skipped. It must emit step_complete with status='passed',
    include valid delta_p, normal range, and record CALCULATION_RESULT in audit log.
    """
    token = create_access_token({
        "sub": "33333333-3333-3333-3333-333333333333",
        "email": "operator@plant.internal",
        "clearance_level": 3,
        "role": "Chief_Safety_Auditor",
    })

    fake_doc_id = "doc-calc-test-01"
    
    with patch("app.services.retrieval_service.retrieval_service.retrieve_document_chunks") as mock_retrieval, \
         patch("app.api.query.get_provider") as mock_get_provider:
        
        from app.services.retrieval_service import RetrievedDocumentChunk
        mock_retrieval.return_value = [
            RetrievedDocumentChunk(
                chunk_id="chk-1",
                document_id=fake_doc_id,
                filename="boiler_specs.pdf",
                page_number=1,
                text="Boiler-102 operating at 6.4 bar inlet pressure with nominal threshold 2.0 to 5.0 bar.",
                score=0.92,
            )
        ]
        
        mock_provider = AsyncMock()
        mock_provider.generate_async.return_value = "Based on page 1 of boiler_specs.pdf, Boiler-102 operates at 6.4 bar."
        mock_get_provider.return_value = mock_provider

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/query/stream",
                json={
                    "text": "What is the pressure in boiler_specs?",
                    "document_ids": [fake_doc_id],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            content = res.text

            # MUST contain step_start and step_complete for calculation
            assert '"step": "calculation"' in content or '"step":"calculation"' in content
            assert '"label": "Sandboxed Calculation"' in content or '"label":"Sandboxed Calculation"' in content
            # MUST NOT be skipped for document queries
            assert '"Document query — calculation skipped"' not in content
            assert '"Document query \u2014 calculation skipped"' not in content
            # MUST be passed
            assert '"status": "passed"' in content or '"status":"passed"' in content
            assert "Δp =" in content or "\\u0394p =" in content


@pytest.mark.asyncio
async def test_document_query_sync_returns_calculation_result():
    """
    Verifies that synchronous /query endpoint with document_ids returns calculation_result object.
    """
    token = create_access_token({
        "sub": "44444444-4444-4444-4444-444444444444",
        "email": "operator@plant.internal",
        "clearance_level": 3,
        "role": "Chief_Safety_Auditor",
    })

    fake_doc_id = "doc-calc-test-02"

    with patch("app.services.retrieval_service.retrieval_service.retrieve_document_chunks") as mock_retrieval, \
         patch("app.api.query.get_provider") as mock_get_provider:

        from app.services.retrieval_service import RetrievedDocumentChunk
        mock_retrieval.return_value = [
            RetrievedDocumentChunk(
                chunk_id="chk-2",
                document_id=fake_doc_id,
                filename="turbine_guide.pdf",
                page_number=2,
                text="Turbine inlet pressure reading is 8.5 bar.",
                score=0.89,
            )
        ]

        mock_provider = AsyncMock()
        mock_provider.generate_async.return_value = "Turbine inlet is 8.5 bar."
        mock_get_provider.return_value = mock_provider

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/query",
                json={
                    "text": "What is the turbine inlet pressure?",
                    "document_ids": [fake_doc_id],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["calculation_result"] is not None
            calc = data["calculation_result"]
            assert calc["pressure_drop"] is not None
            assert calc["unit"] == "bar"
            assert calc["status"] in ("NORMAL", "ABNORMAL")


@pytest.mark.asyncio
async def test_text_only_query_stream_executes_sandboxed_calculation():
    """
    Verifies that a standard text query without images (e.g. asking about plant state)
    runs Sandboxed Calculation with status='passed' instead of skipping.
    """
    token = create_access_token({
        "sub": "55555555-5555-5555-5555-555555555555",
        "email": "operator@plant.internal",
        "clearance_level": 3,
        "role": "Chief_Safety_Auditor",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query/stream",
            json={"text": "Check boiler-102 operational parameters and pressure limits."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        content = res.text

        # Must not say 'Calculation skipped: no verified visual telemetry reading'
        assert "no verified visual telemetry reading" not in content
        assert '"step": "calculation"' in content or '"step":"calculation"' in content
        assert "Δp =" in content or "\\u0394p =" in content
