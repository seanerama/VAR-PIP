"""Pydantic schemas for Category."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    """Base category schema with common fields."""

    name: str
    description: str | None = None


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""

    id: str
    attribute_schema: dict[str, Any] | None = None


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = None
    description: str | None = None
    attribute_schema: dict[str, Any] | None = None


class CategoryResponse(CategoryBase):
    """Schema for category response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    attribute_schema: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class FilterableAttribute(BaseModel):
    """Schema describing a filterable attribute."""

    key: str
    label: str
    type: str  # enum, boolean, integer, number, array
    description: str | None = None
    values: list[str] | None = None  # For enum types


class FilterableAttributesResponse(BaseModel):
    """Response for filterable attributes endpoint."""

    category_id: str
    category_name: str
    attributes: list[FilterableAttribute]
