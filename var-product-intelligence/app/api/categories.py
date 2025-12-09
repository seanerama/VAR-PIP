"""Category API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, CurrentUser
from app.models.category import Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    FilterableAttribute,
    FilterableAttributesResponse,
)

router = APIRouter()


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: DbSession,
    user: CurrentUser,
):
    """List all categories."""
    categories = db.query(Category).all()
    return categories


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get a category by ID."""
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_id}' not found",
        )

    return category


@router.get("/{category_id}/filterable-attributes", response_model=FilterableAttributesResponse)
async def get_filterable_attributes(
    category_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get filterable attributes for a category.

    Returns the attribute schema in a format suitable for building filter UIs.
    """
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_id}' not found",
        )

    if not category.attribute_schema:
        return FilterableAttributesResponse(
            category_id=category.id,
            category_name=category.name,
            attributes=[],
        )

    # Parse schema properties into filterable attributes
    attributes = []
    schema = category.attribute_schema
    properties = schema.get("properties", {})

    for key, prop in properties.items():
        attr = FilterableAttribute(
            key=key,
            label=prop.get("label", key.replace("_", " ").title()),
            type=prop.get("type", "string"),
            description=prop.get("description"),
        )

        # Extract enum values if present
        if "enum" in prop:
            attr.values = prop["enum"]
        elif prop.get("type") == "array" and "items" in prop:
            if "enum" in prop["items"]:
                attr.values = prop["items"]["enum"]

        attributes.append(attr)

    return FilterableAttributesResponse(
        category_id=category.id,
        category_name=category.name,
        attributes=attributes,
    )


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new category."""
    # Check for existing category
    existing = db.query(Category).filter(Category.id == category_in.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{category_in.id}' already exists",
        )

    category = Category(
        id=category_in.id,
        name=category_in.name,
        description=category_in.description,
    )
    category.attribute_schema = category_in.attribute_schema

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    category_in: CategoryUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing category."""
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_id}' not found",
        )

    if category_in.name is not None:
        category.name = category_in.name
    if category_in.description is not None:
        category.description = category_in.description
    if category_in.attribute_schema is not None:
        category.attribute_schema = category_in.attribute_schema

    db.commit()
    db.refresh(category)

    return category
