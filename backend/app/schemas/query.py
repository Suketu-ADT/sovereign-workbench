"""
Query request/response schemas — pipeline is stubbed for Phase 1.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1)
    has_image: bool = False


class QueryResponse(BaseModel):
    status: str
    note: str
