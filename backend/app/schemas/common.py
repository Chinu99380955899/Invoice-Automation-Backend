"""Shared Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base schema that reads attributes off ORM models."""
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error_code: str = Field(..., examples=["VALIDATION_ERROR"])
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Page(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int = 1
    size: int = 20
    pages: int = 1
