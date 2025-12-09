"""Pydantic schemas for product comparison."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class CompareRequest(BaseModel):
    """Schema for comparison request."""

    product_ids: list[str]
    include_pricing: bool = True
    include_attributes: list[str] | None = None  # Empty = all attributes
    title: str | None = None
    notes: str | None = None

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, v):
        """Validate product IDs count."""
        if len(v) < 2:
            raise ValueError("Minimum 2 products required for comparison")
        if len(v) > 10:
            raise ValueError("Maximum 10 products allowed for comparison")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate product IDs are not allowed")
        return v


class CompareResponse(BaseModel):
    """Schema for comparison response."""

    comparison_id: str
    pdf_url: str
    expires_at: datetime
    products_compared: int


class ComparisonNotFoundResponse(BaseModel):
    """Response when comparison PDF is not found or expired."""

    detail: str
    expired: bool = False
