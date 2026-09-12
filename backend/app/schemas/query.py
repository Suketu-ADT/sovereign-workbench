"""
Query request/response schemas for the defense pipeline.
"""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    text: str = Field(default="", max_length=4096)
    message: str | None = Field(default=None, max_length=4096)
    conversation_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    model: str | None = None
    has_image: bool = False
    image_data: str | None = Field(default=None, max_length=10_000_000)  # Max 10MB raw base64 string

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v)
        if "\x00" in s:
            raise ValueError("Null bytes not permitted in query text")
        return s

    def get_query_text(self) -> str:
        """Returns effective query string whether sent as 'text' or 'message'."""
        t = (self.text or "").strip()
        if not t and self.message:
            t = self.message.strip()
        return t


class DocumentCitation(BaseModel):
    filename: str
    page: int
    page_number: int | None = None
    chunk_id: str
    snippet: str = ""

    def model_post_init(self, __context: Any) -> None:
        if self.page_number is None and self.page is not None:
            self.page_number = self.page
        elif self.page is None and self.page_number is not None:
            self.page = self.page_number


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str  # "processed", "ocr_required", "failed"
    page_count: int
    chunk_count: int
    message: str
    format: str = "pdf"
    ocr_applied: bool = False


class RetrievedChunk(BaseModel):
    id: str
    unit: str
    sop_id: str
    title: str
    content: str
    min_clearance: int
    score: float


class VisionResult(BaseModel):
    status: str = "success"  # "success", "skipped", "invalid_image", "extraction_failed"
    reading: float | None = None
    unit: str = "bar"
    parameter: str = "inlet_pressure"
    confidence: float = 0.0
    assessment: str
    error: str | None = None


class CalculationResult(BaseModel):
    formula: str
    inlet_pressure: float
    outlet_pressure: float
    pressure_drop: float
    unit: str = "bar"
    normal_range: str = "2.0 – 5.0 bar"
    status: str  # "NORMAL" or "ABNORMAL"
    is_abnormal: bool
    recommended_action: str | None = None


class HITLApprovalDetails(BaseModel):
    action: str
    target: str
    requestor: str
    context: str
    authority: str
    thread_id: str


class HITLDecisionRequest(BaseModel):
    decision: str  # "approve" or "reject"
    comment: str | None = None


class HITLDecisionResponse(BaseModel):
    thread_id: str
    status: str  # "APPROVED_AND_EXECUTED" or "REJECTED"
    action: str
    target: str
    operator_email: str
    audit_hash: str | None = None
    note: str


class QueryResponse(BaseModel):
    status: str
    note: str
    retrieved_chunks: list[RetrievedChunk] = []
    vision_analysis: VisionResult | None = None
    calculation_result: CalculationResult | None = None
    approval_required: bool = False
    approval_details: HITLApprovalDetails | None = None
    thread_id: str | None = None
    final_synthesis: str | None = None
    model_routing: dict | None = None
    citations: list[DocumentCitation] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
