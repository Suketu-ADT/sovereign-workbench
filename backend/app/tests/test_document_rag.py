"""
Comprehensive End-to-End Test Suite for PDF Document Grounding & RAG.

Covers all 20 required verification cases:
1. Upload PDF
2. PDF successfully parsed
3. Pages extracted
4. Chunks created
5. Embeddings generated
6. Vector index populated
7. Ask factual question
8. Correct chunks retrieved
9. Model receives document context
10. Answer references correct information
11. Citation contains correct page
12. Ask question whose answer is NOT in document
13. Model refuses to invent answer
14. Follow-up question works
15. Multiple documents work
16. Document isolation works
17. Invalid PDF handled
18. Empty/scanned PDF handled
19. Tenant isolation works
20. Delete/remove document works
"""

import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from reportlab.pdfgen import canvas
from pypdf import PdfWriter

from app.main import app
from app.core.security import create_access_token
from app.services.document_service import document_service
from app.services.retrieval_service import retrieval_service
from app.services.model_provider import get_provider


def _create_test_pdf(sections: list[str]) -> bytes:
    """Helper to generate a real, parseable multi-page PDF in memory."""
    bio = io.BytesIO()
    c = canvas.Canvas(bio)
    for idx, text in enumerate(sections, 1):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, 750, f"Section {idx} - Technical Document")
        c.setFont("Helvetica", 10)
        c.drawString(72, 720, text)
        c.drawString(72, 690, "Standard industrial compliance guidelines apply.")
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(72, 50, f"Page {idx} of {len(sections)}")
        c.showPage()
    c.save()
    return bio.getvalue()


@pytest.fixture
def user1_id():
    return str(uuid.uuid4())


@pytest.fixture
def user2_id():
    return str(uuid.uuid4())


@pytest.fixture
def user1_auth(user1_id):
    token = create_access_token({
        "sub": user1_id,
        "email": "operator1@plant.internal",
        "role": "Systems_Specialist",
        "clearance_level": 2,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user2_auth(user2_id):
    token = create_access_token({
        "sub": user2_id,
        "email": "operator2@plant.internal",
        "role": "Systems_Specialist",
        "clearance_level": 2,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def maintenance_pdf_bytes():
    return _create_test_pdf([
        "Plant overview and primary boiler-102 specifications.",
        "The recommended inspection interval is 500 operating hours for all high-pressure feedwater pumps.",
        "Turbine governor calibration must be completed every 1000 operating hours.",
    ])


@pytest.fixture
def safety_pdf_bytes():
    return _create_test_pdf([
        "Emergency battery backup runtime is guaranteed for 48 continuous hours.",
        "Secondary containment nitrogen purge pressure must not exceed 1.8 bar.",
    ])


# ── 1. Upload PDF ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_01_upload_pdf(user1_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("maintenance_report.pdf", maintenance_pdf_bytes, "application/pdf")}
        response = await client.post("/documents/upload", files=files, headers=user1_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["filename"] == "maintenance_report.pdf"
        assert data["page_count"] == 3
        assert data["chunk_count"] >= 3
        assert "document_id" in data


# ── 2. PDF successfully parsed ────────────────────────────────
def test_02_pdf_successfully_parsed(maintenance_pdf_bytes):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(maintenance_pdf_bytes))
    assert len(reader.pages) == 3
    assert not reader.is_encrypted


# ── 3. Pages extracted ─────────────────────────────────────────
def test_03_pages_extracted(maintenance_pdf_bytes):
    pages, is_scanned = document_service.extract_pdf_pages(maintenance_pdf_bytes, "maintenance.pdf")
    assert not is_scanned
    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert "boiler-102" in pages[0].text
    assert pages[1].page_number == 2
    assert "500 operating hours" in pages[1].text


# ── 4. Chunks created ──────────────────────────────────────────
def test_04_chunks_created(maintenance_pdf_bytes):
    pages, _ = document_service.extract_pdf_pages(maintenance_pdf_bytes, "maintenance.pdf")
    chunks = document_service.chunk_extracted_pages(pages, "doc-123", "maintenance.pdf")
    assert len(chunks) >= 3
    for c in chunks:
        assert c.document_id == "doc-123"
        assert c.filename == "maintenance.pdf"
        assert c.page_number in (1, 2, 3)
        assert len(c.text) > 0


# ── 5. Embeddings generated ───────────────────────────────────
def test_05_embeddings_generated():
    vector = retrieval_service.embed_text("Inspection interval is 500 hours")
    assert isinstance(vector, list)
    assert len(vector) == 384
    assert any(v != 0.0 for v in vector)


# ── 6. Vector index populated ─────────────────────────────────
def test_06_vector_index_populated(user1_id, maintenance_pdf_bytes):
    meta = document_service.process_and_index_document(maintenance_pdf_bytes, "report.pdf", user1_id)
    assert meta.status == "processed"
    points_count = retrieval_service.client.count(collection_name="user_documents").count
    assert points_count >= meta.chunk_count


# ── 7. Ask factual question ───────────────────────────────────
@pytest.mark.asyncio
async def test_07_ask_factual_question(user1_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload doc
        files = {"file": ("maintenance_report.pdf", maintenance_pdf_bytes, "application/pdf")}
        up_res = await client.post("/documents/upload", files=files, headers=user1_auth)
        doc_id = up_res.json()["document_id"]

        # Submit question
        query_payload = {
            "text": "What is the recommended inspection interval?",
            "document_ids": [doc_id],
        }
        res = await client.post("/query", json=query_payload, headers=user1_auth)
        assert res.status_code == 200
        data = res.json()
        assert "500 operating hours" in data["final_synthesis"]


# ── 8. Correct chunks retrieved ───────────────────────────────
def test_08_correct_chunks_retrieved(user1_id, maintenance_pdf_bytes):
    meta = document_service.process_and_index_document(maintenance_pdf_bytes, "report.pdf", user1_id)
    chunks = retrieval_service.retrieve_document_chunks(
        query="What is the recommended inspection interval?",
        user_id=user1_id,
        document_ids=[meta.document_id],
        top_k=3,
    )
    assert len(chunks) > 0
    top_chunk = chunks[0]
    assert top_chunk.page_number == 2
    assert "500 operating hours" in top_chunk.text


# ── 9. Model receives document context ────────────────────────
def test_09_model_receives_document_context(user1_id, maintenance_pdf_bytes):
    meta = document_service.process_and_index_document(maintenance_pdf_bytes, "report.pdf", user1_id)
    chunks = retrieval_service.retrieve_document_chunks(
        query="What is the recommended inspection interval?",
        user_id=user1_id,
        document_ids=[meta.document_id],
        top_k=3,
    )
    sys_p, usr_p = document_service.build_grounded_prompt("What is the inspection interval?", chunks)
    assert "DOCUMENT CONTEXT:" in usr_p
    assert "DOCUMENT: report.pdf" in usr_p
    assert "PAGE: 2" in usr_p
    assert "USER QUESTION:" in usr_p
    assert "You are answering questions using the uploaded document" in sys_p


# ── 10. Answer references correct information ─────────────────
@pytest.mark.asyncio
async def test_10_answer_references_correct_information(user1_id, maintenance_pdf_bytes):
    meta = document_service.process_and_index_document(maintenance_pdf_bytes, "report.pdf", user1_id)
    chunks = retrieval_service.retrieve_document_chunks(
        query="What is the recommended inspection interval?",
        user_id=user1_id,
        document_ids=[meta.document_id],
        top_k=3,
    )
    sys_p, usr_p = document_service.build_grounded_prompt("What is the recommended inspection interval?", chunks)
    provider = get_provider("local")
    answer = await provider.generate_async("qwen2.5-32b:local", sys_p, usr_p)
    assert "500 operating hours" in answer


# ── 11. Citation contains correct page ────────────────────────
@pytest.mark.asyncio
async def test_11_citation_contains_correct_page(user1_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("report.pdf", maintenance_pdf_bytes, "application/pdf")}
        up_res = await client.post("/documents/upload", files=files, headers=user1_auth)
        doc_id = up_res.json()["document_id"]

        res = await client.post("/query", json={
            "text": "What is the recommended inspection interval?",
            "document_ids": [doc_id]
        }, headers=user1_auth)
        assert res.status_code == 200
        data = res.json()
        assert "(Page 2)" in data["final_synthesis"] or "Page 2" in data["final_synthesis"]
        assert len(data["citations"]) > 0
        assert data["citations"][0]["page"] == 2
        assert "report.pdf — Page 2" in data["sources"]


# ── 12. Ask question whose answer is NOT in document ──────────
# ── 13. Model refuses to invent answer ─────────────────────────
@pytest.mark.asyncio
async def test_12_13_model_refuses_to_hallucinate(user1_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("report.pdf", maintenance_pdf_bytes, "application/pdf")}
        up_res = await client.post("/documents/upload", files=files, headers=user1_auth)
        doc_id = up_res.json()["document_id"]

        res = await client.post("/query", json={
            "text": "What is the CEO favorite color and car brand?",
            "document_ids": [doc_id]
        }, headers=user1_auth)
        assert res.status_code == 200
        data = res.json()
        assert "I could not find that information in the uploaded document." in data["final_synthesis"]


# ── 14. Follow-up question maintains document context ──────────
@pytest.mark.asyncio
async def test_14_follow_up_question_maintains_context(user1_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("report.pdf", maintenance_pdf_bytes, "application/pdf")}
        up_res = await client.post("/documents/upload", files=files, headers=user1_auth)
        doc_id = up_res.json()["document_id"]

        conv_id = f"conv-{uuid.uuid4().hex[:8]}"

        # First question with explicit document_ids
        q1_res = await client.post("/query", json={
            "text": "What is the recommended inspection interval?",
            "conversation_id": conv_id,
            "document_ids": [doc_id],
        }, headers=user1_auth)
        assert "500 operating hours" in q1_res.json()["final_synthesis"]

        # Follow-up question WITHOUT document_ids (must use conversation memory)
        q2_res = await client.post("/query", json={
            "text": "What is the turbine governor calibration schedule?",
            "conversation_id": conv_id,
        }, headers=user1_auth)
        assert q2_res.status_code == 200
        assert "1000 operating hours" in q2_res.json()["final_synthesis"]
        assert len(q2_res.json()["citations"]) > 0


# ── 15. Multiple documents retrieval ──────────────────────────
@pytest.mark.asyncio
async def test_15_multiple_documents_retrieval(user1_auth, maintenance_pdf_bytes, safety_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload doc 1
        files1 = {"file": ("maint.pdf", maintenance_pdf_bytes, "application/pdf")}
        up1 = await client.post("/documents/upload", files=files1, headers=user1_auth)
        id1 = up1.json()["document_id"]

        # Upload doc 2
        files2 = {"file": ("safety.pdf", safety_pdf_bytes, "application/pdf")}
        up2 = await client.post("/documents/upload", files=files2, headers=user1_auth)
        id2 = up2.json()["document_id"]

        res = await client.post("/query", json={
            "text": "What is the emergency battery backup runtime?",
            "document_ids": [id1, id2],
        }, headers=user1_auth)
        assert res.status_code == 200
        data = res.json()
        assert "48 continuous hours" in data["final_synthesis"]
        assert any("safety.pdf" in src for src in data["sources"])


# ── 16. Document isolation works ──────────────────────────────
@pytest.mark.asyncio
async def test_16_document_isolation(user1_auth, maintenance_pdf_bytes, safety_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload doc 1
        files1 = {"file": ("maint.pdf", maintenance_pdf_bytes, "application/pdf")}
        up1 = await client.post("/documents/upload", files=files1, headers=user1_auth)
        id1 = up1.json()["document_id"]

        # Upload doc 2
        files2 = {"file": ("safety.pdf", safety_pdf_bytes, "application/pdf")}
        up2 = await client.post("/documents/upload", files=files2, headers=user1_auth)
        id2 = up2.json()["document_id"]

        # Ask question about Doc 2, but ONLY pass id1 (Doc 1)
        res = await client.post("/query", json={
            "text": "What is the emergency battery backup runtime?",
            "document_ids": [id1],
        }, headers=user1_auth)
        assert res.status_code == 200
        # Doc 1 does NOT have battery runtime; MUST NOT retrieve chunks from Doc 2
        assert "I could not find that information in the uploaded document." in res.json()["final_synthesis"]
        for c in res.json()["citations"]:
            assert c["filename"] == "maint.pdf"
            assert c["filename"] != "safety.pdf"


# ── 17. Invalid PDF handled ───────────────────────────────────
@pytest.mark.asyncio
async def test_17_invalid_pdf_handled(user1_auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        corrupted_bytes = b"This is not a real PDF file structure"
        files = {"file": ("corrupt.pdf", corrupted_bytes, "application/pdf")}
        response = await client.post("/documents/upload", files=files, headers=user1_auth)
        assert response.status_code == 400
        detail = response.json()["detail"]
        error_msg = detail if isinstance(detail, str) else detail.get("error", str(detail))
        assert "Invalid PDF" in error_msg


# ── 18. Empty/scanned PDF handled ─────────────────────────────
@pytest.mark.asyncio
async def test_18_empty_scanned_pdf_handled(user1_auth):
    # Blank PDF with no text
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    bio = io.BytesIO()
    writer.write(bio)
    blank_pdf = bio.getvalue()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("scanned.pdf", blank_pdf, "application/pdf")}
        response = await client.post("/documents/upload", files=files, headers=user1_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ocr_required"
        assert "OCR is required" in data["message"]
        assert data["chunk_count"] == 0


# ── 19. Tenant isolation works ────────────────────────────────
@pytest.mark.asyncio
async def test_19_tenant_isolation(user1_auth, user2_auth, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User 1 uploads document
        files = {"file": ("confidential.pdf", maintenance_pdf_bytes, "application/pdf")}
        up = await client.post("/documents/upload", files=files, headers=user1_auth)
        user1_doc_id = up.json()["document_id"]

        # User 2 attempts to query User 1's document
        res = await client.post("/query", json={
            "text": "What is the recommended inspection interval?",
            "document_ids": [user1_doc_id],
        }, headers=user2_auth)
        assert res.status_code == 200
        # Chunks are filtered by user_id == operator2, so 0 chunks returned
        assert "I could not find that information in the uploaded document." in res.json()["final_synthesis"]

        # User 2 attempts to DELETE User 1's document
        del_res = await client.delete(f"/documents/{user1_doc_id}", headers=user2_auth)
        assert del_res.status_code == 404


# ── 20. Delete/remove document works ──────────────────────────
@pytest.mark.asyncio
async def test_20_delete_document_works(user1_auth, user1_id, maintenance_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload
        files = {"file": ("to_delete.pdf", maintenance_pdf_bytes, "application/pdf")}
        up = await client.post("/documents/upload", files=files, headers=user1_auth)
        doc_id = up.json()["document_id"]

        # Verify exists in memory
        assert document_service.get_document(doc_id, user1_id) is not None

        # Delete
        del_res = await client.delete(f"/documents/{doc_id}", headers=user1_auth)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify no longer exists
        assert document_service.get_document(doc_id, user1_id) is None
        get_res = await client.get(f"/documents/{doc_id}", headers=user1_auth)
        assert get_res.status_code == 404
