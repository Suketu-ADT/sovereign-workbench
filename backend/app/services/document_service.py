"""
Sovereign Workbench Universal Document Ingestion, OCR & RAG Service.
Handles multi-format document validation, on-premise RapidOCR text extraction,
page/slide/sheet/row provenance preservation, boundary-preserving chunking,
embedding generation, Qdrant vector indexing, and strict document isolation.

Supported Formats:
- PDF (.pdf) with digital text extraction and scanned image OCR
- Microsoft Word (.docx, .doc)
- Microsoft PowerPoint (.pptx, .ppt)
- Microsoft Excel (.xlsx, .xls)
- Delimited text (.csv, .tsv)
- Structured data & code (.json, .txt, .md, .yaml, .yml, .log)
- Standalone Images (.png, .jpg, .jpeg, .tiff, .bmp, .webp) with RapidOCR
"""

import csv
import io
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pypdf
from pydantic import BaseModel

from app.core.config import settings
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)

# Maximum allowed document upload size (25 MB)
MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024

SUPPORTED_EXTENSIONS = {
    # PDFs
    ".pdf": "pdf",
    # Office Word
    ".docx": "docx",
    ".doc": "docx",
    # Office PowerPoint
    ".pptx": "pptx",
    ".ppt": "pptx",
    # Office Excel
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    # Tabular / Delimited
    ".csv": "csv",
    ".tsv": "csv",
    # Structured & Text
    ".json": "json",
    ".txt": "text",
    ".md": "text",
    ".log": "text",
    ".yaml": "text",
    ".yml": "text",
    # Images (for direct OCR)
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".webp": "image",
}


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    image_count: int = 0
    ocr_applied: bool = False
    section_label: str = ""


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    text: str


@dataclass
class DocumentMetadata:
    document_id: str
    user_id: str
    filename: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str  # "processed", "ocr_required", "failed"
    message: str
    created_at: str
    format: str = "pdf"
    ocr_applied: bool = False


class DocumentService:
    """Manages multi-format document validation, OCR extraction, chunking, and indexing."""

    def __init__(self):
        # In-memory document registry: document_id -> DocumentMetadata
        self._documents: Dict[str, DocumentMetadata] = {}
        # Active conversation documents: conversation_id -> list of document_ids
        self._conversation_docs: Dict[str, List[str]] = {}
        # Lazy initialized RapidOCR engine
        self._ocr_engine = None

    def _get_ocr_engine(self):
        """Lazy-initializes on-premise RapidOCR engine running on ONNX Runtime."""
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                logger.info("Initializing RapidOCR engine on ONNX Runtime...")
                self._ocr_engine = RapidOCR()
                logger.info("RapidOCR engine initialized successfully.")
            except Exception as e:
                logger.warning("RapidOCR initialization warning: %s", e)
                self._ocr_engine = False
        return self._ocr_engine if self._ocr_engine is not False else None

    def extract_text_with_ocr(self, image_data: Any) -> str:
        """
        Executes on-premise, self-contained RapidOCR on raw image bytes or PIL Image.
        Returns extracted text string with normalized whitespace.
        """
        engine = self._get_ocr_engine()
        if not engine:
            logger.debug("OCR engine not available; skipping OCR extraction.")
            return ""

        try:
            from PIL import Image
            import numpy as np

            if isinstance(image_data, bytes):
                pil_img = Image.open(io.BytesIO(image_data))
            elif hasattr(image_data, "convert"):
                pil_img = image_data
            else:
                return ""

            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            np_img = np.array(pil_img)
            results, _ = engine(np_img)
            if not results:
                return ""

            lines = [item[1].strip() for item in results if item and len(item) > 1 and item[1].strip()]
            extracted_text = " ".join(lines)
            return re.sub(r"\s+", " ", extracted_text).strip()
        except Exception as ocr_err:
            logger.warning("RapidOCR execution error on image: %s", ocr_err)
            return ""

    def validate_document(self, file_bytes: bytes, filename: str) -> str:
        """
        Validates document extension, byte size, and header signature across all supported formats.
        Returns normalized format string (e.g. 'pdf', 'docx', 'xlsx', 'pptx', 'csv', 'json', 'text', 'image').
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported_list = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
            raise ValueError(f"Unsupported document format '{ext}'. Supported formats: {supported_list}")

        if len(file_bytes) == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")

        if len(file_bytes) > MAX_DOCUMENT_SIZE_BYTES:
            max_mb = MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"File exceeds maximum allowed size of {max_mb} MB.")

        doc_format = SUPPORTED_EXTENSIONS[ext]

        if doc_format == "pdf":
            if not file_bytes.startswith(b"%PDF"):
                raise ValueError("Invalid PDF format: missing '%PDF' header signature.")
        elif doc_format in ("docx", "pptx", "xlsx"):
            # Office XML files are ZIP containers starting with PK\x03\x04
            if not file_bytes.startswith(b"PK\x03\x04") and not ext in (".doc", ".ppt", ".xls"):
                raise ValueError(f"Invalid {ext} file: missing valid package signature.")
        elif doc_format == "image":
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes))
                img.verify()
            except Exception as img_err:
                raise ValueError(f"Invalid or corrupted image format: {img_err}")

        return doc_format

    def validate_pdf(self, file_bytes: bytes, filename: str) -> None:
        """Backward-compatible validation helper for PDF documents."""
        self.validate_document(file_bytes, filename)

    # ── PDF Extraction (Digital + Scanned OCR) ──────────────────────
    def extract_pdf_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """
        Extracts text page-by-page from PDF. If digital text on a page is negligible (<50 chars)
        and embedded images are present, automatically runs on-premise RapidOCR on the images.
        Returns: (pages, is_scanned_unreadable, any_ocr_applied)
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            logger.error("Failed to parse PDF stream for '%s': %s", filename, e)
            raise ValueError(f"Corrupt or unreadable PDF document: {e}")

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise ValueError("PDF document contains zero pages.")

        pages: List[ExtractedPage] = []
        total_text_length = 0
        total_images = 0
        any_ocr_applied = False

        for i, page in enumerate(reader.pages):
            page_num = i + 1
            raw_text = ""
            try:
                raw_text = page.extract_text() or ""
            except Exception as extract_err:
                logger.warning("Text extraction warning on page %d of '%s': %s", page_num, filename, extract_err)

            normalized = re.sub(r"[ \t]+", " ", raw_text).strip()
            normalized = re.sub(r"\n\s*\n+", "\n\n", normalized)

            img_count = 0
            page_ocr_text = ""
            page_ocr_applied = False

            if hasattr(page, "images") and page.images:
                try:
                    img_count = len(page.images)
                except Exception:
                    img_count = 1

                # If page has very little digital text, execute on-premise OCR on embedded images
                if len(normalized) < 50 and img_count > 0:
                    try:
                        for img_obj in page.images:
                            ocr_t = self.extract_text_with_ocr(img_obj.data)
                            if ocr_t:
                                page_ocr_text = (page_ocr_text + " " + ocr_t).strip()
                                page_ocr_applied = True
                                any_ocr_applied = True
                    except Exception as ocr_page_err:
                        logger.debug("Page %d OCR image sweep: %s", page_num, ocr_page_err)

            final_page_text = normalized
            if page_ocr_text:
                final_page_text = (final_page_text + "\n" + page_ocr_text).strip()

            total_text_length += len(final_page_text)
            total_images += img_count

            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=final_page_text,
                    image_count=img_count,
                    ocr_applied=page_ocr_applied,
                    section_label=f"Page {page_num}",
                )
            )

        # Scanned unreadable:
        # If OCR was applied and extracted readable text, the document is successfully read.
        # If no OCR was applied, digital text must be >= 50 chars to avoid scanned PDF warning.
        if any_ocr_applied:
            is_scanned_unreadable = (total_text_length < 15)
        else:
            is_scanned_unreadable = (total_text_length < 50)

        return pages, is_scanned_unreadable

    # ── Word (.docx) Extraction ────────────────────────────────────
    def extract_docx_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Extracts text, headings, and tables from Word (.docx) documents."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
        except Exception as e:
            logger.error("Failed to parse Word document '%s': %s", filename, e)
            raise ValueError(f"Corrupt or unreadable Word (.docx) document: {e}")

        pages: List[ExtractedPage] = []
        current_page_text = []
        page_num = 1
        word_count = 0

        # Extract paragraphs
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue

            # Heading or new section break
            if p.style and "heading" in p.style.name.lower():
                txt = f"\n### {txt}\n"

            current_page_text.append(txt)
            word_count += len(txt.split())

            # Group every ~400 words into a logical document page
            if word_count >= 400:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n\n".join(current_page_text).strip(),
                        section_label=f"Section/Page {page_num}",
                    )
                )
                page_num += 1
                current_page_text = []
                word_count = 0

        # Extract tables
        for t_idx, table in enumerate(doc.tables):
            table_lines = [f"\n[Table {t_idx + 1}]"]
            for row in table.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    table_lines.append(" | ".join(row_cells))
            t_content = "\n".join(table_lines)
            current_page_text.append(t_content)
            word_count += len(t_content.split())
            if word_count >= 400:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n\n".join(current_page_text).strip(),
                        section_label=f"Section/Page {page_num}",
                    )
                )
                page_num += 1
                current_page_text = []
                word_count = 0

        if current_page_text or not pages:
            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text="\n\n".join(current_page_text).strip() if current_page_text else "Document Content",
                    section_label=f"Section/Page {page_num}",
                )
            )

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── PowerPoint (.pptx) Extraction ──────────────────────────────
    def extract_pptx_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Extracts slide-by-slide text, titles, notes, and tables from PowerPoint presentations."""
        try:
            import pptx
            prs = pptx.Presentation(io.BytesIO(file_bytes))
        except Exception as e:
            logger.error("Failed to parse PowerPoint presentation '%s': %s", filename, e)
            raise ValueError(f"Corrupt or unreadable PowerPoint (.pptx) presentation: {e}")

        pages: List[ExtractedPage] = []
        for i, slide in enumerate(prs.slides):
            slide_num = i + 1
            slide_lines = []

            # Extract slide title
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_lines.append(f"Slide Title: {slide.shapes.title.text.strip()}")

            # Extract all shapes and textframes
            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_text_frame:
                    t = shape.text_frame.text.strip()
                    if t:
                        slide_lines.append(t)
                elif shape.has_table:
                    for row in shape.table.rows:
                        row_vals = [c.text.strip() for c in row.cells if c.text.strip()]
                        if row_vals:
                            slide_lines.append(" | ".join(row_vals))

            # Extract speaker notes if present
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    slide_lines.append(f"Notes: {notes_text}")

            full_slide_text = "\n".join(slide_lines).strip()
            pages.append(
                ExtractedPage(
                    page_number=slide_num,
                    text=full_slide_text,
                    section_label=f"Slide {slide_num}",
                )
            )

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── Excel (.xlsx) Extraction ───────────────────────────────────
    def extract_xlsx_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Extracts sheets and formatted tabular rows from Excel spreadsheets."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        except Exception as e:
            logger.error("Failed to parse Excel workbook '%s': %s", filename, e)
            raise ValueError(f"Corrupt or unreadable Excel (.xlsx) spreadsheet: {e}")

        pages: List[ExtractedPage] = []
        page_num = 1

        for sheetname in wb.sheetnames:
            sheet = wb[sheetname]
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue

            # First row as header
            header = [str(c).strip() if c is not None else f"Col_{idx}" for idx, c in enumerate(rows[0])]
            batch_lines = [f"Spreadsheet Sheet: {sheetname}"]

            for r_idx, row in enumerate(rows[1:], start=2):
                row_items = []
                for h, val in zip(header, row):
                    if val is not None and str(val).strip():
                        row_items.append(f"{h}: {val}")
                if row_items:
                    batch_lines.append(f"Row {r_idx}: " + ", ".join(row_items))

                # Batch every 50 rows into a logical page
                if len(batch_lines) >= 50:
                    pages.append(
                        ExtractedPage(
                            page_number=page_num,
                            text="\n".join(batch_lines).strip(),
                            section_label=f"Sheet '{sheetname}' Page {page_num}",
                        )
                    )
                    page_num += 1
                    batch_lines = [f"Spreadsheet Sheet: {sheetname}"]

            if len(batch_lines) > 1:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n".join(batch_lines).strip(),
                        section_label=f"Sheet '{sheetname}' Page {page_num}",
                    )
                )
                page_num += 1

        if not pages:
            pages.append(ExtractedPage(page_number=1, text="", section_label="Empty Spreadsheet"))

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── Delimited Text (.csv / .tsv) Extraction ────────────────────
    def extract_csv_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Extracts structured tabular records from CSV or TSV files."""
        try:
            text_content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = file_bytes.decode("latin-1", errors="ignore")

        delim = "\t" if filename.lower().endswith(".tsv") else ","
        f_obj = io.StringIO(text_content)
        reader = csv.reader(f_obj, delimiter=delim)

        rows = list(reader)
        if not rows:
            return [ExtractedPage(page_number=1, text="")], True, False

        header = [c.strip() if c.strip() else f"Col_{i}" for i, c in enumerate(rows[0])]
        pages: List[ExtractedPage] = []
        page_num = 1
        batch_lines = [f"Tabular Data: {filename}"]

        for r_idx, row in enumerate(rows[1:], start=2):
            items = []
            for h, val in zip(header, row):
                if val.strip():
                    items.append(f"{h}: {val.strip()}")
            if items:
                batch_lines.append(f"Row {r_idx}: " + ", ".join(items))

            if len(batch_lines) >= 50:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n".join(batch_lines).strip(),
                        section_label=f"Records Page {page_num}",
                    )
                )
                page_num += 1
                batch_lines = [f"Tabular Data: {filename}"]

        if len(batch_lines) > 1 or not pages:
            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text="\n".join(batch_lines).strip(),
                    section_label=f"Records Page {page_num}",
                )
            )

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── JSON Extraction ────────────────────────────────────────────
    def extract_json_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Parses structured JSON records or configuration objects into human-readable text."""
        try:
            data = json.loads(file_bytes.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to parse JSON file '%s': %s", filename, e)
            raise ValueError(f"Invalid or corrupted JSON document: {e}")

        pages: List[ExtractedPage] = []
        page_num = 1

        if isinstance(data, list):
            # List of records
            batch_records = []
            for idx, item in enumerate(data, start=1):
                batch_records.append(f"Record #{idx}:\n{json.dumps(item, indent=2)}")
                if len(batch_records) >= 10:
                    pages.append(
                        ExtractedPage(
                            page_number=page_num,
                            text="\n\n".join(batch_records).strip(),
                            section_label=f"JSON Records {page_num}",
                        )
                    )
                    page_num += 1
                    batch_records = []
            if batch_records:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n\n".join(batch_records).strip(),
                        section_label=f"JSON Records {page_num}",
                    )
                )
        else:
            # Single object or hierarchical dictionary
            formatted_json = json.dumps(data, indent=2)
            lines = formatted_json.split("\n")
            # Chunk every 100 lines
            for i in range(0, len(lines), 100):
                chunk_lines = lines[i : i + 100]
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="\n".join(chunk_lines).strip(),
                        section_label=f"JSON Page {page_num}",
                    )
                )
                page_num += 1

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── Plain Text / Markdown / Log Extraction ─────────────────────
    def extract_text_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Extracts text from plain text, Markdown, logs, and YAML files."""
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("latin-1", errors="ignore")

        lines = content.splitlines()
        pages: List[ExtractedPage] = []
        page_num = 1

        # Group every 60 lines into a page
        for i in range(0, max(1, len(lines)), 60):
            block = "\n".join(lines[i : i + 60]).strip()
            if block:
                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=block,
                        section_label=f"Page {page_num}",
                    )
                )
                page_num += 1

        if not pages:
            pages.append(ExtractedPage(page_number=1, text="", section_label="Empty Text Document"))

        is_empty = all(len(p.text.strip()) == 0 for p in pages)
        return pages, is_empty, False

    # ── Standalone Image OCR Extraction ────────────────────────────
    def extract_image_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool]:
        """Performs on-premise RapidOCR directly on standalone image files."""
        text = self.extract_text_with_ocr(file_bytes)
        pages = [
            ExtractedPage(
                page_number=1,
                text=text,
                image_count=1,
                ocr_applied=True,
                section_label="OCR Scanned Image",
            )
        ]
        is_empty = len(text.strip()) == 0
        return pages, is_empty, True

    # ── Master Document Extraction Dispatcher ──────────────────────
    def extract_document_pages(self, file_bytes: bytes, filename: str) -> Tuple[List[ExtractedPage], bool, bool, str]:
        """
        Validates and dispatches file to format-specific parser or OCR extractor.
        Returns: (pages, is_scanned_unreadable, ocr_applied, doc_format)
        """
        doc_format = self.validate_document(file_bytes, filename)

        if doc_format == "pdf":
            pages, is_scanned = self.extract_pdf_pages(file_bytes, filename)
            ocr_applied = any(p.ocr_applied for p in pages)
        elif doc_format == "docx":
            pages, is_scanned, ocr_applied = self.extract_docx_pages(file_bytes, filename)
        elif doc_format == "pptx":
            pages, is_scanned, ocr_applied = self.extract_pptx_pages(file_bytes, filename)
        elif doc_format == "xlsx":
            pages, is_scanned, ocr_applied = self.extract_xlsx_pages(file_bytes, filename)
        elif doc_format == "csv":
            pages, is_scanned, ocr_applied = self.extract_csv_pages(file_bytes, filename)
        elif doc_format == "json":
            pages, is_scanned, ocr_applied = self.extract_json_pages(file_bytes, filename)
        elif doc_format == "text":
            pages, is_scanned, ocr_applied = self.extract_text_pages(file_bytes, filename)
        elif doc_format == "image":
            pages, is_scanned, ocr_applied = self.extract_image_pages(file_bytes, filename)
        else:
            raise ValueError(f"No extractor implemented for format '{doc_format}'")

        return pages, is_scanned, ocr_applied, doc_format

    # ── Provenance-Preserving Chunking ─────────────────────────────
    def chunk_document(
        self,
        document_id: str,
        filename: str,
        pages: List[ExtractedPage],
        chunk_size: int = 800,
        overlap: int = 100,
    ) -> List[DocumentChunk]:
        """
        Splits extracted pages into chunks while preserving sentence/paragraph boundaries
        and retaining precise page / slide / sheet number provenance.
        """
        chunks: List[DocumentChunk] = []
        chunk_counter = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            # If the page text fits into a single chunk, keep it intact
            if len(text) <= chunk_size:
                chunk_counter += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}-p{page.page_number}-c{chunk_counter}",
                        document_id=document_id,
                        filename=filename,
                        page_number=page.page_number,
                        text=text,
                    )
                )
                continue

            # Split by double newlines (paragraphs) first, or fallback to sentences
            paragraphs = re.split(r"\n\n+", text)
            current_buf = ""

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                if len(current_buf) + len(para) + 2 <= chunk_size:
                    current_buf = (current_buf + "\n\n" + para).strip()
                else:
                    if current_buf:
                        chunk_counter += 1
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{document_id}-p{page.page_number}-c{chunk_counter}",
                                document_id=document_id,
                                filename=filename,
                                page_number=page.page_number,
                                text=current_buf,
                            )
                        )
                        # Carry over overlap
                        current_buf = current_buf[-overlap:] if len(current_buf) > overlap else ""

                    # If paragraph itself is longer than chunk_size, split by sentences
                    if len(para) > chunk_size:
                        sentences = re.split(r"(?<=[.?!])\s+", para)
                        for sent in sentences:
                            sent = sent.strip()
                            if not sent:
                                continue
                            if len(current_buf) + len(sent) + 1 <= chunk_size:
                                current_buf = (current_buf + " " + sent).strip()
                            else:
                                if current_buf:
                                    chunk_counter += 1
                                    chunks.append(
                                        DocumentChunk(
                                            chunk_id=f"{document_id}-p{page.page_number}-c{chunk_counter}",
                                            document_id=document_id,
                                            filename=filename,
                                            page_number=page.page_number,
                                            text=current_buf,
                                        )
                                    )
                                    current_buf = current_buf[-overlap:] if len(current_buf) > overlap else ""
                                current_buf = (current_buf + " " + sent).strip()
                    else:
                        current_buf = (current_buf + "\n\n" + para).strip()

            if current_buf.strip():
                chunk_counter += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}-p{page.page_number}-c{chunk_counter}",
                        document_id=document_id,
                        filename=filename,
                        page_number=page.page_number,
                        text=current_buf.strip(),
                    )
                )

        return chunks

    def chunk_extracted_pages(
        self,
        pages: List[ExtractedPage],
        document_id: str,
        filename: str,
        chunk_size: int = 800,
        overlap: int = 100,
    ) -> List[DocumentChunk]:
        """Convenience alias for chunk_document."""
        return self.chunk_document(
            document_id=document_id,
            filename=filename,
            pages=pages,
            chunk_size=chunk_size,
            overlap=overlap,
        )

    # ── End-to-End Ingestion Pipeline ──────────────────────────────
    def process_and_index_document(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
    ) -> DocumentMetadata:
        """
        Universal multi-format ingestion pipeline:
        Validation -> Text / OCR Extraction -> Chunking -> Embeddings -> Qdrant.
        """
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        pages, is_scanned_unreadable, ocr_applied, doc_format = self.extract_document_pages(file_bytes, filename)
        page_count = len(pages)

        if is_scanned_unreadable:
            msg = (
                "This appears to be a scanned document or contains no extractable text. "
                "OCR was unable to detect readable characters."
                if ocr_applied or doc_format == "image"
                else "This appears to be a scanned PDF. OCR is required."
            )
            meta = DocumentMetadata(
                document_id=doc_id,
                user_id=user_id,
                filename=filename,
                file_size=len(file_bytes),
                page_count=page_count,
                chunk_count=0,
                status="ocr_required",
                message=msg,
                created_at=created_at,
                format=doc_format,
                ocr_applied=ocr_applied,
            )
            self._documents[doc_id] = meta
            logger.info("Scanned unreadable document detected for '%s' (doc_id=%s, format=%s).", filename, doc_id, doc_format)
            return meta

        chunks = self.chunk_document(doc_id, filename, pages)
        if not chunks:
            meta = DocumentMetadata(
                document_id=doc_id,
                user_id=user_id,
                filename=filename,
                file_size=len(file_bytes),
                page_count=page_count,
                chunk_count=0,
                status="ocr_required",
                message="Document contains no extractable text chunks. OCR is required.",
                created_at=created_at,
                format=doc_format,
                ocr_applied=ocr_applied,
            )
            self._documents[doc_id] = meta
            return meta

        # Index chunks into Qdrant collection user_documents
        try:
            retrieval_service.index_user_chunks(user_id=user_id, chunks=chunks)
            status_str = "processed"
            ocr_note = " (OCR text extracted)" if ocr_applied else ""
            msg = f"Document processed{ocr_note} and {len(chunks)} chunks indexed"
        except Exception as e:
            logger.error("Failed to index chunks into Qdrant for doc_id=%s: %s", doc_id, e)
            meta = DocumentMetadata(
                document_id=doc_id,
                user_id=user_id,
                filename=filename,
                file_size=len(file_bytes),
                page_count=page_count,
                chunk_count=0,
                status="failed",
                message=f"Document indexing failed: {e}",
                created_at=created_at,
                format=doc_format,
                ocr_applied=ocr_applied,
            )
            self._documents[doc_id] = meta
            return meta

        meta = DocumentMetadata(
            document_id=doc_id,
            user_id=user_id,
            filename=filename,
            file_size=len(file_bytes),
            page_count=page_count,
            chunk_count=len(chunks),
            status=status_str,
            message=msg,
            created_at=created_at,
            format=doc_format,
            ocr_applied=ocr_applied,
        )
        self._documents[doc_id] = meta
        logger.info(
            "Successfully indexed document '%s' (format=%s, %d pages/slides, %d chunks, doc_id=%s, ocr=%s)",
            filename,
            doc_format,
            page_count,
            len(chunks),
            doc_id,
            ocr_applied,
        )
        return meta

    def get_document(self, document_id: str, user_id: Optional[str] = None) -> Optional[DocumentMetadata]:
        doc = self._documents.get(document_id)
        if not doc:
            return None
        if user_id and str(doc.user_id) != str(user_id):
            return None
        return doc

    def delete_document(self, document_id: str, user_id: str) -> bool:
        """Purges document metadata and removes its chunks from Qdrant."""
        doc = self._documents.get(document_id)
        if not doc:
            return False

        if str(doc.user_id) != str(user_id):
            logger.warning("Unauthorized attempt by user %s to delete document %s (owner: %s)", user_id, document_id, doc.user_id)
            return False

        # Purge chunks from Qdrant
        try:
            retrieval_service.delete_user_document_chunks(document_id=document_id, user_id=user_id)
        except Exception as e:
            logger.error("Failed to purge Qdrant points for doc_id=%s: %s", document_id, e)

        # Remove from active conversation docs
        for conv_id in list(self._conversation_docs.keys()):
            if document_id in self._conversation_docs[conv_id]:
                self._conversation_docs[conv_id].remove(document_id)

        del self._documents[document_id]
        logger.info("Deleted document %s for user %s", document_id, user_id)
        return True

    def set_conversation_document(self, conversation_id: str, document_id: Any) -> None:
        """Associates document(s) with a conversation so follow-ups retain context."""
        if not conversation_id or not document_id:
            return
        if conversation_id not in self._conversation_docs:
            self._conversation_docs[conversation_id] = []
        if isinstance(document_id, (list, tuple, set)):
            for did in document_id:
                if did and did not in self._conversation_docs[conversation_id]:
                    self._conversation_docs[conversation_id].append(did)
        else:
            if document_id not in self._conversation_docs[conversation_id]:
                self._conversation_docs[conversation_id].append(document_id)

    def get_conversation_documents(self, conversation_id: str) -> List[str]:
        """Returns the active document IDs associated with a conversation."""
        if not conversation_id:
            return []
        return list(self._conversation_docs.get(conversation_id, []))

    # ── Grounded Prompt Construction ──────────────────────────────
    def build_grounded_prompt(
        self,
        user_question: str = "",
        retrieved_chunks: Optional[List[Any]] = None,
        query: str = "",
        chunks: Optional[List[Any]] = None,
    ) -> Tuple[str, str]:
        """
        Constructs system instructions enforcing zero-hallucination document answering
        and a user prompt combining retrieved chunks with the question.
        Accepts flexible parameter names (user_question/query, retrieved_chunks/chunks).
        """
        question = user_question or query
        chunks_list = retrieved_chunks if retrieved_chunks is not None else (chunks or [])

        system_instruction = (
            "You are answering questions using the uploaded document.\n\n"
            "Use the provided document context as the primary source of truth.\n"
            "Do not invent facts that are not supported by the document.\n"
            "If the answer cannot be found in the provided document context, explicitly say:\n"
            "'I could not find that information in the uploaded document.'\n\n"
            "When possible, cite the relevant page number, for example: '(Page 7)'."
        )

        context_parts = []
        for c in chunks_list:
            doc_name = getattr(c, "filename", "document")
            page_num = getattr(c, "page_number", getattr(c, "page", 1))
            txt = getattr(c, "text", "")
            context_parts.append(f"DOCUMENT: {doc_name}\nPAGE: {page_num}\n{txt}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant document chunks retrieved."
        user_prompt = f"DOCUMENT CONTEXT:\n{context_str}\n\nUSER QUESTION:\n{question}"
        return system_instruction, user_prompt


# Global singleton instance
document_service = DocumentService()
