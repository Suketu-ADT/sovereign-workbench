"""
Query request/response schemas for the defense pipeline.
"""

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    has_image: bool = False
    image_data: str | None = Field(default=None, max_length=10_000_000)  # Max 10MB raw base64 string

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("Null bytes not permitted in query text")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query text cannot be empty whitespace")
        return stripped


class RetrievedChunk(BaseModel):
    id: str
    unit: str
    sop_id: str
    title: str
    content: str
    min_clearance: int
    score: float


class VisionResult(BaseModel):
    status: str = "success"  # "success", "skipped", "invalid_image"
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
