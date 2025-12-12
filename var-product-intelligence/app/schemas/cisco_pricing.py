"""Pydantic schemas for Cisco pricing integration."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CiscoPriceSyncRequest(BaseModel):
    """Request schema for syncing Cisco prices."""
    skus: list[str] | None = Field(
        None,
        description="Specific SKUs to sync. If None, syncs all Cisco products in database."
    )
    price_list: str = Field(
        default="GLUS",
        description="Cisco price list code (GLUS=US, GLEMEA=EMEA, etc.)"
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Number of SKUs per API request (max 200 to avoid rate limits)"
    )
    delay_between_batches: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Seconds to wait between batch requests"
    )
    update_eol_info: bool = Field(
        default=False,
        description="Also fetch End-of-Life dates"
    )
    dry_run: bool = Field(
        default=False,
        description="Preview changes without saving"
    )


class CiscoPriceSyncItem(BaseModel):
    """Single item result from price sync."""
    sku: str
    old_price: float | None = None
    new_price: float | None = None
    currency: str | None = None
    action: Literal["updated", "unchanged", "not_found", "error"]
    message: str | None = None
    eol_date: str | None = None
    lead_time: str | None = None


class CiscoPriceSyncResponse(BaseModel):
    """Response schema for price sync."""
    success: bool
    price_list: str
    dry_run: bool

    # Counts
    total_requested: int
    found: int
    updated: int
    unchanged: int
    not_found: int
    errors: int

    # Timing
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    # Details (limited to avoid huge responses)
    items: list[CiscoPriceSyncItem] = []
    warnings: list[str] = []


class CiscoPriceLookupRequest(BaseModel):
    """Request for real-time price lookup (not saved to DB)."""
    skus: list[str] = Field(
        description="SKUs to look up (max 50 for real-time)"
    )
    price_list: str = Field(
        default="GLUS",
        description="Cisco price list code"
    )
    include_availability: bool = Field(
        default=False,
        description="Include availability/lead time info"
    )
    include_eol: bool = Field(
        default=False,
        description="Include End-of-Life dates"
    )


class CiscoPriceInfo(BaseModel):
    """Price information for a single SKU."""
    sku: str
    description: str | None = None
    list_price: float | None = None
    currency: str | None = None
    product_type: str | None = None
    erp_family: str | None = None

    # Availability (if requested)
    web_orderable: str | None = None
    lead_time: str | None = None
    stockable: str | None = None

    # EOL (if requested)
    end_of_sale_date: str | None = None
    last_date_of_support: str | None = None

    # Error handling
    error: str | None = None


class CiscoPriceLookupResponse(BaseModel):
    """Response for real-time price lookup."""
    price_list: str
    total: int
    found: int
    not_found: int
    items: list[CiscoPriceInfo]
