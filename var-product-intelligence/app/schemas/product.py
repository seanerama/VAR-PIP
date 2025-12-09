"""Pydantic schemas for Product."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    """Base product schema with common fields."""

    sku: str
    vendor_id: str
    category_id: str
    name: str
    product_family: str | None = None
    list_price: float | None = None
    cost_price: float | None = None
    currency: str = "USD"
    lifecycle_status: str = "active"
    warranty_years: int | None = None
    attributes: dict[str, Any] | None = None
    datasheet_url: str | None = None
    image_url: str | None = None
    notes: str | None = None


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    sku: str | None = None
    vendor_id: str | None = None
    category_id: str | None = None
    name: str | None = None
    product_family: str | None = None
    list_price: float | None = None
    cost_price: float | None = None
    currency: str | None = None
    lifecycle_status: str | None = None
    warranty_years: int | None = None
    attributes: dict[str, Any] | None = None
    datasheet_url: str | None = None
    image_url: str | None = None
    notes: str | None = None


class ProductResponse(BaseModel):
    """Schema for product response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    vendor_id: str
    category_id: str
    name: str
    product_family: str | None = None
    list_price: float | None = None
    cost_price: float | None = None
    currency: str
    lifecycle_status: str
    warranty_years: int | None = None
    attributes: dict[str, Any] | None = None
    datasheet_url: str | None = None
    image_url: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    # Nested vendor and category names
    vendor_name: str | None = None
    category_name: str | None = None


class ProductListResponse(BaseModel):
    """Schema for paginated product list response."""

    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
