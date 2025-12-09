"""Pydantic schemas for Vendor."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VendorBase(BaseModel):
    """Base vendor schema with common fields."""

    name: str
    website: str | None = None
    partner_portal_url: str | None = None


class VendorCreate(VendorBase):
    """Schema for creating a vendor."""

    id: str


class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""

    name: str | None = None
    website: str | None = None
    partner_portal_url: str | None = None


class VendorResponse(VendorBase):
    """Schema for vendor response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
