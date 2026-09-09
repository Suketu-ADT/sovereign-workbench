"""
Query request/response schemas for the defense pipeline.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1)
    has_image: bool = False
    image_data: str | None = None  # Base64 data URL or raw base64 string


class RetrievedChunk(BaseModel):
    id: str
    unit: str
    sop_id: str
    title: str
    content: str
    min_clearance: int
    score: float


class VisionResult(BaseModel):
    reading: float
    unit: str = "bar"
    parameter: str = "inlet_pressure"
    confidence: float
    assessment: str


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


class QueryResponse(BaseModel):
    status: str
    note: str
    retrieved_chunks: list[RetrievedChunk] = []
    vision_analysis: VisionResult | None = None
    calculation_result: CalculationResult | None = None
