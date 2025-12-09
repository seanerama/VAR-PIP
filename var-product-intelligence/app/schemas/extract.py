"""Pydantic schemas for AI datasheet extraction."""

from typing import Any

from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    """Schema for datasheet extraction request."""

    category_id: str
    vendor_id: str
    file_content: str  # Base64-encoded PDF
    filename: str


class ExtractedField(BaseModel):
    """Schema for a single extracted field."""

    value: Any
    confidence: str  # high, medium, low
    source_note: str | None = None


class ExtractedProduct(BaseModel):
    """Schema for extracted product data."""

    sku: str | None = None
    name: str | None = None
    product_family: str | None = None
    attributes: dict[str, ExtractedField] = {}


class ExtractionResponse(BaseModel):
    """Schema for extraction response."""

    extraction_id: str
    status: str  # completed, partial, failed
    confidence_score: float  # 0.0 to 1.0
    extracted_product: ExtractedProduct
    warnings: list[str] = []
    vendor_created: bool = False  # True if vendor was auto-created


class ExtractionErrorResponse(BaseModel):
    """Response for extraction errors."""

    detail: str
    extraction_id: str | None = None
