"""Vendor API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, CurrentUser
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse

router = APIRouter()


@router.get("", response_model=list[VendorResponse])
async def list_vendors(
    db: DbSession,
    user: CurrentUser,
):
    """List all vendors."""
    vendors = db.query(Vendor).all()
    return vendors


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get a vendor by ID."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()

    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found",
        )

    return vendor


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor_in: VendorCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new vendor."""
    # Check for existing vendor
    existing = db.query(Vendor).filter(Vendor.id == vendor_in.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vendor '{vendor_in.id}' already exists",
        )

    vendor = Vendor(
        id=vendor_in.id,
        name=vendor_in.name,
        website=vendor_in.website,
        partner_portal_url=vendor_in.partner_portal_url,
    )

    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return vendor


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    vendor_in: VendorUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing vendor."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()

    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found",
        )

    if vendor_in.name is not None:
        vendor.name = vendor_in.name
    if vendor_in.website is not None:
        vendor.website = vendor_in.website
    if vendor_in.partner_portal_url is not None:
        vendor.partner_portal_url = vendor_in.partner_portal_url

    db.commit()
    db.refresh(vendor)

    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a vendor.

    Note: This will fail if the vendor has associated products.
    """
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()

    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found",
        )

    # Check for associated products
    if vendor.products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete vendor '{vendor_id}' - has {len(vendor.products)} associated products",
        )

    db.delete(vendor)
    db.commit()
