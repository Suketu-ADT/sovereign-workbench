"""
Universal Document RAG & On-Premise OCR Test Suite.
Verifies end-to-end ingestion, on-premise RapidOCR text extraction,
and grounded RAG querying across all supported formats:
1. Scanned PDF with embedded image OCR
2. Word document (.docx)
3. PowerPoint presentation (.pptx)
4. Excel spreadsheet (.xlsx)
5. CSV delimited data (.csv)
6. Structured JSON (.json)
7. Plain text / Markdown (.md)
8. Standalone image (.png) with direct RapidOCR
9. Anti-hallucination refusal across formats
10. Document deletion and vector cleanup
"""

import csv
import io
import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw
import pypdf
import docx
import pptx
import openpyxl

from app.main import app
from app.core.security import create_access_token
from app.services.document_service import document_service
from app.services.retrieval_service import retrieval_service


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers():
    token = create_access_token({
        "sub": str(uuid.uuid4()),
        "username": "universal_operator",
        "role": "Systems_Specialist",
        "clearance_level": 2,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def scanned_pdf_bytes():
    """Generates a scanned PDF with an image containing rendered text."""
    img = Image.new("RGB", (700, 120), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 40), "Feedwater Valve FV-904 setpoint is 45.5 bar pressure.", fill=(0, 0, 0))

    img_buf = io.BytesIO()
    img.save(img_buf, format="PDF")
    return img_buf.getvalue()


@pytest.fixture
def docx_bytes():
    """Generates a sample Word (.docx) document."""
    d = docx.Document()
    d.add_heading("Compressor Maintenance Procedures", level=1)
    d.add_paragraph("The primary compressor oil filter must be replaced every 250 operating hours.")
    table = d.add_table(rows=1, cols=2)
    hdr = table.rows[0].cells
    hdr[0].text = "Parameter"
    hdr[1].text = "Nominal Value"
    row = table.add_row().cells
    row[0].text = "Suction Pressure"
    row[1].text = "2.4 bar"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def pptx_bytes():
    """Generates a sample PowerPoint (.pptx) presentation."""
    prs = pptx.Presentation()
    # Slide 1
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "Turbine Fleet Overview"
    slide1.placeholders[1].text = "Fleet vibration analysis and vibration alert limits."
    # Slide 2
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Generator Cooling"
    slide2.placeholders[1].text = "Hydrogen cooling pressure must be maintained at 3.0 bar continuous."
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def xlsx_bytes():
    """Generates a sample Excel (.xlsx) workbook."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Telemetry Limits"
    ws.append(["Component", "Normal Range", "Trip Limit"])
    ws.append(["Boiler 102", "12.0 - 15.0 bar", "18.5 bar"])
    ws.append(["Condenser Pump", "40 - 55 C", "68 C"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def csv_bytes():
    """Generates a sample CSV file."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Subsystem", "Inspection Cycle", "Responsible Team"])
    writer.writerow(["Emergency Diesel Generator", "Every 15 days", "Electrical Dept"])
    writer.writerow(["Fire Suppression Sprinklers", "Every 30 days", "Safety Team"])
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def json_bytes():
    """Generates a structured JSON file."""
    data = {
        "plant_id": "PLANT-NORTH-04",
        "emergency_procedures": {
            "steam_isolation": "Manual valve shutoff valve SV-101 closes in 4 seconds.",
            "backup_power_generator": "Uninterruptible power supply duration is 72 hours."
        }
    }
    return json.dumps(data, indent=2).encode("utf-8")


@pytest.fixture
def ocr_image_bytes():
    """Generates a standalone PNG image with known text."""
    img = Image.new("RGB", (650, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 35), "Digital Dial Gauge Reading: Inlet 6.8 bar Outlet 3.2 bar", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Tests ─────────────────────────────────────────────────────────────

# 1. Scanned PDF with RapidOCR
@pytest.mark.asyncio
async def test_01_scanned_pdf_ocr_extraction(auth_headers, scanned_pdf_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("scanned_valve.pdf", scanned_pdf_bytes, "application/pdf")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["chunk_count"] > 0
        assert data["ocr_applied"] is True
        doc_id = data["document_id"]

        # Query factual question extracted via OCR
        q_res = await client.post("/query", json={
            "text": "What is the feedwater valve FV-904 setpoint?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "45.5 bar" in ans or "FV-904" in ans


# 2. Blank / Empty PDF Detection
@pytest.mark.asyncio
async def test_02_empty_pdf_detection(auth_headers):
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("blank.pdf", buf.getvalue(), "application/pdf")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ocr_required"
        assert data["chunk_count"] == 0


# 3. Microsoft Word (.docx)
@pytest.mark.asyncio
async def test_03_word_docx_extraction_and_rag(auth_headers, docx_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("compressor_manual.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "docx"
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "When must the compressor oil filter be replaced?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "250 operating hours" in ans


# 4. Microsoft PowerPoint (.pptx)
@pytest.mark.asyncio
async def test_04_powerpoint_pptx_extraction_and_rag(auth_headers, pptx_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("generator_briefing.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "pptx"
        assert data["page_count"] == 2  # 2 slides
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "What is the required hydrogen cooling pressure?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "3.0 bar" in ans


# 5. Microsoft Excel (.xlsx)
@pytest.mark.asyncio
async def test_05_excel_xlsx_extraction_and_rag(auth_headers, xlsx_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("telemetry_limits.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "xlsx"
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "What is the trip limit for Boiler 102?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "18.5 bar" in ans


# 6. CSV Delimited Data
@pytest.mark.asyncio
async def test_06_csv_extraction_and_rag(auth_headers, csv_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("inspection_cycles.csv", csv_bytes, "text/csv")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "csv"
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "What is the inspection cycle for the Emergency Diesel Generator?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "15 days" in ans


# 7. Structured JSON
@pytest.mark.asyncio
async def test_07_json_extraction_and_rag(auth_headers, json_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("plant_emergency.json", json_bytes, "application/json")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "json"
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "How long is the uninterruptible power supply duration?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "72 hours" in ans


# 8. Standalone Image with Direct RapidOCR
@pytest.mark.asyncio
async def test_08_image_ocr_extraction_and_rag(auth_headers, ocr_image_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("dial_reading.png", ocr_image_bytes, "image/png")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["format"] == "image"
        assert data["ocr_applied"] is True
        assert data["chunk_count"] > 0
        doc_id = data["document_id"]

        q_res = await client.post("/query", json={
            "text": "What is the inlet pressure reading from the dial gauge?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "6.8" in ans


# 9. Anti-Hallucination Refusal across Formats
@pytest.mark.asyncio
async def test_09_anti_hallucination_refusal(auth_headers, json_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("specs.json", json_bytes, "application/json")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        doc_id = res.json()["document_id"]

        q_res = await client.post("/query", json={
            "text": "What is the plant manager's favorite movie?",
            "document_ids": [doc_id],
        }, headers=auth_headers)
        assert q_res.status_code == 200
        ans = q_res.json()["final_synthesis"]
        assert "I could not find that information in the uploaded document." in ans


# 10. Document Deletion & Vector Purge
@pytest.mark.asyncio
async def test_10_document_deletion(auth_headers, csv_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("temp_data.csv", csv_bytes, "text/csv")}
        res = await client.post("/documents/upload", files=files, headers=auth_headers)
        doc_id = res.json()["document_id"]

        # Delete
        del_res = await client.delete(f"/documents/{doc_id}", headers=auth_headers)
        assert del_res.status_code == 200
        # Subsequent get returns 404
        get_res = await client.get(f"/documents/{doc_id}", headers=auth_headers)
        assert get_res.status_code == 404
