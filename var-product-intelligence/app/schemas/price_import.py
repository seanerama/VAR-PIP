"""Pydantic schemas for price import functionality."""

from typing import Literal

from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Column mapping for CSV import."""
    sku_column: str = Field(description="Column name containing SKU/part number")
    price_column: str = Field(description="Column name containing price")
    name_column: str | None = Field(None, description="Optional column for product name")
    description_column: str | None = Field(None, description="Optional column for description")
    vendor_column: str | None = Field(None, description="Optional column for vendor/manufacturer")


class PriceImportRequest(BaseModel):
    """Request schema for importing prices from CSV."""
    file_path: str = Field(description="Path to CSV file")

    # Price type
    price_type: Literal["list", "cost"] = Field(
        default="list",
        description="Whether importing list prices or cost prices"
    )

    # Column mapping - use preset or custom
    format: Literal["auto", "generic", "ingram", "synnex", "dnh", "custom"] = Field(
        default="auto",
        description="CSV format preset or 'custom' for manual column mapping"
    )
    custom_mapping: ColumnMapping | None = Field(
        None,
        description="Custom column mapping (required if format='custom')"
    )

    # Import options
    vendor_id: str | None = Field(
        None,
        description="Override vendor for all imported prices"
    )
    category_id: str | None = Field(
        None,
        description="Override category for new products"
    )
    create_missing: bool = Field(
        default=False,
        description="Create products that don't exist in database"
    )
    update_existing: bool = Field(
        default=True,
        description="Update prices for existing products"
    )
    dry_run: bool = Field(
        default=False,
        description="Preview changes without saving"
    )


class PriceImportItem(BaseModel):
    """Single item result from price import."""
    sku: str
    name: str | None = None
    old_price: float | None = None
    new_price: float
    action: Literal["created", "updated", "skipped", "error"]
    message: str | None = None


class PriceImportResponse(BaseModel):
    """Response schema for price import."""
    success: bool
    file_path: str
    format_detected: str
    price_type: str

    # Counts
    total_rows: int
    matched: int
    created: int
    updated: int
    skipped: int
    errors: int

    # Details
    items: list[PriceImportItem] = []
    warnings: list[str] = []

    # Dry run indicator
    dry_run: bool = False


class PriceExportRequest(BaseModel):
    """Request schema for exporting prices to CSV."""
    file_path: str = Field(description="Output file path")
    vendor_id: str | None = Field(None, description="Filter by vendor")
    category_id: str | None = Field(None, description="Filter by category")
    include_cost: bool = Field(default=False, description="Include cost prices")
    format: Literal["generic", "detailed"] = Field(default="generic")


class PriceExportResponse(BaseModel):
    """Response schema for price export."""
    success: bool
    file_path: str
    total_products: int
    with_prices: int
    without_prices: int
