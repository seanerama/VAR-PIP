"""Filter service for dynamic product queries."""

import json
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, Query

from app.models.product import Product


class FilterService:
    """Service for building dynamic product queries."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def build_query(
        self,
        category: str | None = None,
        vendors: list[str] | None = None,
        lifecycle_status: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        attribute_filters: dict[str, Any] | None = None,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> Query:
        """Build a SQLAlchemy query with the given filters.

        Args:
            category: Filter by category ID
            vendors: Filter by vendor IDs (multiple allowed)
            lifecycle_status: Filter by lifecycle status
            min_price: Minimum list price
            max_price: Maximum list price
            attribute_filters: JSON attribute filters
            search: Search term for name, SKU, product_family
            sort_by: Sort field (name, list_price, sku, updated_at)
            sort_order: Sort direction (asc, desc)

        Returns:
            SQLAlchemy Query object
        """
        query = self.db.query(Product)

        # Category filter
        if category:
            query = query.filter(Product.category_id == category)

        # Vendor filter (can be multiple)
        if vendors:
            query = query.filter(Product.vendor_id.in_(vendors))

        # Lifecycle status filter
        if lifecycle_status:
            query = query.filter(Product.lifecycle_status == lifecycle_status)

        # Price range filters
        if min_price is not None:
            query = query.filter(Product.list_price >= min_price)
        if max_price is not None:
            query = query.filter(Product.list_price <= max_price)

        # Attribute filters (JSON-based)
        if attribute_filters:
            query = self._apply_attribute_filters(query, attribute_filters)

        # Search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                    Product.product_family.ilike(search_term),
                )
            )

        # Sorting
        query = self._apply_sorting(query, sort_by, sort_order)

        return query

    def _apply_attribute_filters(
        self, query: Query, filters: dict[str, Any]
    ) -> Query:
        """Apply JSON attribute filters to query.

        For SQLite, we use JSON functions via the stored TEXT column.

        Args:
            query: Current query
            filters: Dictionary of attribute key -> value(s) to filter

        Returns:
            Modified query with attribute filters
        """
        for key, value in filters.items():
            if isinstance(value, list):
                # Array filter - match any of the values
                # For SQLite, we need to check if any value matches
                conditions = []
                for v in value:
                    if isinstance(v, bool):
                        # Boolean: check for true/false string in JSON
                        json_val = "true" if v else "false"
                        conditions.append(
                            Product._attributes.like(f'%"{key}": {json_val}%')
                        )
                    elif isinstance(v, str):
                        conditions.append(
                            Product._attributes.like(f'%"{key}": "{v}"%')
                        )
                    else:
                        conditions.append(
                            Product._attributes.like(f'%"{key}": {v}%')
                        )
                if conditions:
                    query = query.filter(or_(*conditions))
            elif isinstance(value, bool):
                # Boolean filter
                json_val = "true" if value else "false"
                query = query.filter(
                    Product._attributes.like(f'%"{key}": {json_val}%')
                )
            elif isinstance(value, str):
                # String equality
                query = query.filter(
                    Product._attributes.like(f'%"{key}": "{value}"%')
                )
            else:
                # Numeric equality
                query = query.filter(
                    Product._attributes.like(f'%"{key}": {value}%')
                )

        return query

    def _apply_sorting(
        self, query: Query, sort_by: str, sort_order: str
    ) -> Query:
        """Apply sorting to query.

        Args:
            query: Current query
            sort_by: Field to sort by
            sort_order: asc or desc

        Returns:
            Modified query with sorting
        """
        # Map sort_by to actual columns
        sort_columns = {
            "name": Product.name,
            "list_price": Product.list_price,
            "sku": Product.sku,
            "updated_at": Product.updated_at,
            "created_at": Product.created_at,
        }

        column = sort_columns.get(sort_by, Product.name)

        if sort_order.lower() == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())

        return query

    def execute_with_pagination(
        self, query: Query, skip: int = 0, limit: int = 50
    ) -> tuple[list[Product], int]:
        """Execute query with pagination and return results with total count.

        Args:
            query: SQLAlchemy query to execute
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (products list, total count)
        """
        total = query.count()
        products = query.offset(skip).limit(limit).all()
        return products, total
