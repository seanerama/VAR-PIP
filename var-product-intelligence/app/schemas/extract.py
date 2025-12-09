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


class UrlExtractionRequest(BaseModel):
    """Schema for URL-based extraction request."""

    url: str
    category_id: str
    vendor_id: str


class PdfLink(BaseModel):
    """Schema for a discovered PDF link."""

    url: str
    title: str | None = None


class UrlExtractionResponse(BaseModel):
    """Schema for URL extraction response.

    source_type indicates what was found:
    - "pdf": Direct PDF, extraction completed
    - "html": HTML page with inline specs, extraction completed
    - "pdf_listing": HTML page with PDF links found, user should select
    """

    extraction_id: str
    source_type: str  # pdf, html, pdf_listing
    source_url: str

    # For pdf and html source types - extraction results
    status: str | None = None  # completed, partial, failed
    confidence_score: float | None = None
    extracted_product: ExtractedProduct | None = None
    warnings: list[str] = []
    vendor_created: bool = False

    # For pdf_listing source type - list of PDFs found
    pdf_links_found: list[PdfLink] = []


class BatchUrlExtractionRequest(BaseModel):
    """Schema for batch extraction from multiple PDF URLs."""

    pdf_urls: list[str]
    category_id: str
    vendor_id: str


class BatchExtractionResult(BaseModel):
    """Result for a single item in batch extraction."""

    url: str
    success: bool
    extraction_id: str | None = None
    status: str | None = None
    confidence_score: float | None = None
    extracted_product: ExtractedProduct | None = None
    warnings: list[str] = []
    error: str | None = None


class BatchUrlExtractionResponse(BaseModel):
    """Schema for batch URL extraction response."""

    total: int
    successful: int
    failed: int
    results: list[BatchExtractionResult]
    vendor_created: bool = False
