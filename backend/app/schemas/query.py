"""
Query request/response schemas for the defense pipeline.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1)
    has_image: bool = False


class RetrievedChunk(BaseModel):
    id: str
    unit: str
    sop_id: str
    title: str
    content: str
    min_clearance: int
    score: float


class QueryResponse(BaseModel):
    status: str
    note: str
    retrieved_chunks: list[RetrievedChunk] = []
