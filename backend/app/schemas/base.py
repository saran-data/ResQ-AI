"""
ResQAI - Base Pydantic Schemas
Shared response wrappers and pagination models used across all endpoints.
"""

from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with shared configuration for all ResQAI schemas."""
    model_config = ConfigDict(
        from_attributes=True,           # Allow ORM model → schema conversion
        populate_by_name=True,          # Accept both alias and field name
        use_enum_values=True,           # Serialize enums as values
        str_strip_whitespace=True,      # Auto-strip string whitespace
        validate_assignment=True,       # Validate on attribute assignment
    )


class TimestampSchema(BaseSchema):
    """Mixin adding created_at / updated_at to any response schema."""
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseSchema):
    """Standard pagination query parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginationMeta(BaseSchema):
    """Pagination metadata included in list responses."""
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, page: int, page_size: int, total: int) -> "PaginationMeta":
        total_pages = max(1, (total + page_size - 1) // page_size)
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ApiResponse(BaseSchema, Generic[T]):
    """Standard API response envelope for single-item responses."""
    success: bool = True
    data: T
    message: Optional[str] = None
    request_id: Optional[str] = None

    @classmethod
    def ok(cls, data: T, message: Optional[str] = None) -> "ApiResponse[T]":
        return cls(success=True, data=data, message=message)


class PaginatedResponse(BaseSchema, Generic[T]):
    """Standard API response envelope for paginated list responses."""
    success: bool = True
    data: List[T]
    pagination: PaginationMeta
    message: Optional[str] = None
    request_id: Optional[str] = None

    @classmethod
    def ok(
        cls,
        data: List[T],
        page: int,
        page_size: int,
        total: int,
        message: Optional[str] = None,
    ) -> "PaginatedResponse[T]":
        return cls(
            success=True,
            data=data,
            pagination=PaginationMeta.build(page, page_size, total),
            message=message,
        )


class ErrorDetail(BaseSchema):
    """Error detail for validation errors."""
    field: Optional[str] = None
    message: str
    type: str


class ErrorResponse(BaseSchema):
    """Standard error response envelope."""
    success: bool = False
    error: dict
    request_id: Optional[str] = None


class MessageResponse(BaseSchema):
    """Simple message-only response."""
    success: bool = True
    message: str


class IDResponse(BaseSchema):
    """Response containing only a created/updated resource ID."""
    success: bool = True
    id: UUID
    message: Optional[str] = None
