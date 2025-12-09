"""Product API endpoints."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, CurrentUser
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)
from app.services.product_service import ProductService
from app.services.filter_service import FilterService

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    db: DbSession,
    user: CurrentUser,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    category: str | None = Query(None, description="Category ID filter"),
    vendor: list[str] | None = Query(None, description="Vendor ID(s) filter"),
    lifecycle_status: str | None = Query(None, description="Lifecycle status filter"),
    min_price: float | None = Query(None, description="Minimum list price"),
    max_price: float | None = Query(None, description="Maximum list price"),
    attribute_filters: str | None = Query(
        None, description="JSON string of attribute filters"
    ),
    search: str | None = Query(None, description="Search in name, SKU, product family"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order (asc/desc)"),
):
    """List and filter products.

    Use attribute_filters as a JSON string to filter by category-specific attributes.
    Example: {"wifi_generation": "wifi6e", "form_factor": ["indoor", "outdoor"]}
    """
    # Parse attribute filters if provided
    parsed_filters: dict[str, Any] | None = None
    if attribute_filters:
        try:
            parsed_filters = json.loads(attribute_filters)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in attribute_filters parameter",
            )

    filter_service = FilterService(db)
    query = filter_service.build_query(
        category=category,
        vendors=vendor,
        lifecycle_status=lifecycle_status,
        min_price=min_price,
        max_price=max_price,
        attribute_filters=parsed_filters,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    products, total = filter_service.execute_with_pagination(query, skip, limit)

    product_service = ProductService(db)
    items = [product_service.enrich_with_names(p) for p in products]

    return ProductListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get a product by ID."""
    product_service = ProductService(db)
    product = product_service.get(product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )

    return product_service.enrich_with_names(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new product."""
    product_service = ProductService(db)

    # Validate vendor exists
    if not product_service.validate_vendor_exists(product_in.vendor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vendor '{product_in.vendor_id}' does not exist",
        )

    # Validate category exists
    if not product_service.validate_category_exists(product_in.category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{product_in.category_id}' does not exist",
        )

    # Check for duplicate SKU
    existing = product_service.get_by_sku(product_in.sku)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{product_in.sku}' already exists",
        )

    product = product_service.create(product_in)
    return product_service.enrich_with_names(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_in: ProductUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing product."""
    product_service = ProductService(db)
    product = product_service.get(product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )

    # Validate vendor if being updated
    if product_in.vendor_id and not product_service.validate_vendor_exists(
        product_in.vendor_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vendor '{product_in.vendor_id}' does not exist",
        )

    # Validate category if being updated
    if product_in.category_id and not product_service.validate_category_exists(
        product_in.category_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{product_in.category_id}' does not exist",
        )

    # Check for duplicate SKU if being updated
    if product_in.sku and product_in.sku != product.sku:
        existing = product_service.get_by_sku(product_in.sku)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with SKU '{product_in.sku}' already exists",
            )

    product = product_service.update(product, product_in)
    return product_service.enrich_with_names(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a product."""
    product_service = ProductService(db)
    product = product_service.get(product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )

    product_service.delete(product)
