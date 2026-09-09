"""
Phase 3 test suite: RBAC-Filtered Vector Retrieval (Qdrant + FastEmbed + Clearance Tagging).
Tests:
  1. Ingestion and vector embedding of plant operational manuals
  2. RBAC database pre-filtering: Level 1 cannot retrieve Level 2 or Level 3 chunks
  3. RBAC database pre-filtering: Level 2 can retrieve Level 1 and 2, but not Level 3
  4. RBAC database pre-filtering: Level 3 can retrieve all levels
  5. Full API pipeline integration: POST /query returns role-filtered chunks and emits RETRIEVAL_CHUNKS_ACCESSED audit event
  6. Cryptographic audit verification of retrieval events
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.plant_manuals import PLANT_MANUAL_CHUNKS
from app.main import app
from app.services.retrieval_service import RetrievalService, retrieval_service


def test_retrieval_service_seeding():
    """Verify that all operational manual chunks are correctly seeded into Qdrant."""
    assert retrieval_service._initialized is True
    count = retrieval_service.client.count(collection_name=retrieval_service.collection_name).count
    assert count == len(PLANT_MANUAL_CHUNKS)
    assert count == 9


def test_retrieval_rbac_prefilter_level_1():
    """Level 1 operator must only receive chunks with min_clearance <= 1."""
    # Querying boiler operating parameters
    boiler_results = retrieval_service.retrieve(
        query="What is the operating drum pressure for boiler-102?",
        operator_clearance=1,
        top_k=3,
    )
    assert len(boiler_results) > 0
    assert all(c.min_clearance <= 1 for c in boiler_results)
    assert all(c.unit == "boiler-102" for c in boiler_results)
    assert any("SOP-102-1" in c.sop_id for c in boiler_results)

    # Even if Level 1 asks about turbine or reactor topics, Qdrant pre-filter must exclude L2 and L3 vectors
    forbidden_results = retrieval_service.retrieve(
        query="What is the vibration trip threshold and SCRAM timing?",
        operator_clearance=1,
        top_k=3,
    )
    assert all(c.min_clearance <= 1 for c in forbidden_results)
    assert all(c.unit != "turbine-gen-4" for c in forbidden_results)
    assert all(c.unit != "reactor-core-aux" for c in forbidden_results)


def test_retrieval_rbac_prefilter_level_2():
    """Level 2 operator can access Level 1 and Level 2, but NEVER Level 3."""
    # Querying turbine rotor dynamics
    turbine_results = retrieval_service.retrieve(
        query="What is the vibration velocity alarm and trip limit for turbine-gen-4?",
        operator_clearance=2,
        top_k=3,
    )
    assert len(turbine_results) > 0
    assert all(c.min_clearance <= 2 for c in turbine_results)
    # The top result should be the turbine vibration SOP
    assert turbine_results[0].sop_id == "SOP-204-1"
    assert turbine_results[0].unit == "turbine-gen-4"
    assert turbine_results[0].min_clearance == 2

    # Querying reactor topics at Level 2 must exclude Level 3
    reactor_query_results = retrieval_service.retrieve(
        query="What is the emergency core cooling accumulator pressure and rod drop time?",
        operator_clearance=2,
        top_k=5,
    )
    assert all(c.min_clearance <= 2 for c in reactor_query_results)
    assert all(c.unit != "reactor-core-aux" for c in reactor_query_results)


def test_retrieval_rbac_prefilter_level_3():
    """Level 3 operator can access all operational documents including Level 3."""
    results = retrieval_service.retrieve(
        query="What is the emergency SCRAM insertion timing for reactor-core-aux?",
        operator_clearance=3,
        top_k=3,
    )
    assert len(results) > 0
    assert results[0].sop_id == "SOP-301-1"
    assert results[0].unit == "reactor-core-aux"
    assert results[0].min_clearance == 3
    assert "1.80 seconds" in results[0].content


@pytest.mark.asyncio
async def test_query_pipeline_retrieval_integration():
    """
    Test end-to-end /query pipeline:
    1. Login as Level 1 operator (John Morrison)
    2. Submit query about boiler-102
    3. Assert response contains retrieved_chunks
    4. Assert all retrieved chunks have min_clearance <= 1
    5. Assert RETRIEVAL_CHUNKS_ACCESSED is recorded on the audit log
    6. Assert GET /audit/verify confirms 100% hash chain validity
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login John Morrison (Level 1)
        login_res = await client.post(
            "/auth/login",
            json={"email": "j.morrison@plant.internal", "password": "changeme123"},
        )
        assert login_res.status_code == 200
        token_l1 = login_res.json()["access_token"]
        headers_l1 = {"Authorization": f"Bearer {token_l1}"}

        # Submit operational query about boiler-102
        query_res = await client.post(
            "/query",
            json={"text": "Check normal operating pressure envelope for boiler-102"},
            headers=headers_l1,
        )
        assert query_res.status_code == 200
        data = query_res.json()
        assert data["status"] == "accepted_stub"
        assert "retrieved_chunks" in data
        assert len(data["retrieved_chunks"]) > 0

        # Verify all retrieved chunks respect Level 1 clearance
        for chunk in data["retrieved_chunks"]:
            assert chunk["min_clearance"] <= 1
            assert chunk["unit"] == "boiler-102"
        assert data["retrieved_chunks"][0]["sop_id"] == "SOP-102-1"

        # Verify audit log contains RETRIEVAL_CHUNKS_ACCESSED
        audit_res = await client.get("/audit?limit=20", headers=headers_l1)
        assert audit_res.status_code == 200
        entries = audit_res.json()["entries"]
        retrieval_entries = [e for e in entries if e["event"] == "RETRIEVAL_CHUNKS_ACCESSED"]
        assert len(retrieval_entries) > 0
        latest_retrieval = retrieval_entries[0]
        assert "SOP-102-1" in latest_retrieval["detail"]
        assert "clearance 1" in latest_retrieval["detail"]


        # Verify cryptographic hash chain integrity
        verify_res = await client.get("/audit/verify", headers=headers_l1)
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["valid"] is True
        assert verify_data["broken_at_index"] is None
        assert verify_data["entries_checked"] > 0

