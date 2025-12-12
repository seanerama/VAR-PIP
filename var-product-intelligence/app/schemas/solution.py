"""Pydantic schemas for solutions and BOM generation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ============== Component Schemas ==============

class SolutionComponentBase(BaseModel):
    """Base schema for solution components."""
    name: str
    component_type: Literal["controller", "edge", "license", "subscription", "software", "optional"]
    description: str | None = None
    is_required: bool = True
    display_order: int = 0
    quantity_type: Literal["fixed", "per_site", "per_device", "per_user", "calculated"] = "fixed"
    quantity_default: int = 1
    quantity_formula: str | None = None
    sizing_tiers: list[dict] | None = None
    product_options: list[str] | None = None
    license_type: Literal["subscription", "perpetual", "term"] | None = None
    license_tiers: list[str] | None = None
    license_term_months: list[int] | None = None
    license_per_unit: str | None = None
    dependencies: list[str] | None = None
    notes: str | None = None
    features: list[str] | None = None


class SolutionComponentCreate(SolutionComponentBase):
    """Schema for creating a solution component."""
    pass


class SolutionComponentResponse(SolutionComponentBase):
    """Schema for solution component response."""
    id: str
    solution_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Solution Schemas ==============

class SolutionBase(BaseModel):
    """Base schema for solutions."""
    name: str
    vendor_id: str
    solution_type: str  # "sdwan", "wireless", "security", "switching"
    description: str | None = None
    use_cases: list[str] | None = None
    documentation_url: str | None = None


class SolutionCreate(SolutionBase):
    """Schema for creating a solution."""
    components: list[SolutionComponentCreate] | None = None


class SolutionSummary(BaseModel):
    """Brief solution summary for listing."""
    id: str
    name: str
    vendor_id: str
    vendor_name: str | None = None
    solution_type: str
    description: str | None = None
    component_count: int = 0

    class Config:
        from_attributes = True


class SolutionResponse(SolutionBase):
    """Full solution response with components."""
    id: str
    created_at: datetime
    updated_at: datetime
    components: list[SolutionComponentResponse] = []

    class Config:
        from_attributes = True


# ============== BOM Request/Response Schemas ==============

class BOMRequest(BaseModel):
    """Request schema for generating a Bill of Materials."""
    solution_id: str

    # Sizing parameters (user provides based on solution type)
    sites: int | None = None
    devices: int | None = None  # APs, edge routers, etc.
    users: int | None = None

    # Options
    license_tier: str | None = None  # "essentials", "advantage", "premier"
    license_term_years: int | None = Field(None, ge=1, le=7)
    ha_enabled: bool = True  # High availability for controllers

    # Selected product options (component_id -> selected SKU)
    product_selections: dict[str, str] | None = None


class BOMLineItem(BaseModel):
    """Single line item in a Bill of Materials."""
    component_id: str
    component_name: str
    component_type: str
    quantity: int
    sku: str | None = None
    product_name: str | None = None
    unit_price: float | None = None
    extended_price: float | None = None
    license_tier: str | None = None
    license_term_months: int | None = None
    notes: str | None = None
    is_required: bool = True


class BOMResponse(BaseModel):
    """Response schema for Bill of Materials."""
    solution_id: str
    solution_name: str
    vendor_id: str
    vendor_name: str | None = None

    # Input parameters used
    parameters: dict

    # BOM line items
    line_items: list[BOMLineItem]

    # Totals
    hardware_total: float | None = None
    licensing_total: float | None = None
    grand_total: float | None = None

    # Additional info
    notes: list[str] = []
    warnings: list[str] = []


# ============== Solution List Schemas ==============

class SolutionListRequest(BaseModel):
    """Request schema for listing solutions."""
    vendor_id: str | None = None
    solution_type: str | None = None


class SolutionListResponse(BaseModel):
    """Response schema for solution list."""
    solutions: list[SolutionSummary]
    total: int
