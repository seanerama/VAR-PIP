"""Product service for CRUD operations."""

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.vendor import Vendor
from app.models.category import Category
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    """Service for product CRUD operations."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def get(self, product_id: str) -> Product | None:
        """Get a product by ID."""
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_by_sku(self, sku: str) -> Product | None:
        """Get a product by SKU."""
        return self.db.query(Product).filter(Product.sku == sku).first()

    def get_multi(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        """Get multiple products with pagination."""
        return self.db.query(Product).offset(skip).limit(limit).all()

    def get_by_ids(self, product_ids: list[str]) -> list[Product]:
        """Get multiple products by their IDs."""
        return self.db.query(Product).filter(Product.id.in_(product_ids)).all()

    def create(self, product_in: ProductCreate) -> Product:
        """Create a new product."""
        product = Product(
            sku=product_in.sku,
            vendor_id=product_in.vendor_id,
            category_id=product_in.category_id,
            name=product_in.name,
            product_family=product_in.product_family,
            list_price=product_in.list_price,
            cost_price=product_in.cost_price,
            currency=product_in.currency,
            lifecycle_status=product_in.lifecycle_status,
            warranty_years=product_in.warranty_years,
            datasheet_url=product_in.datasheet_url,
            image_url=product_in.image_url,
            notes=product_in.notes,
        )
        product.attributes = product_in.attributes

        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update(self, product: Product, product_in: ProductUpdate) -> Product:
        """Update an existing product."""
        update_data = product_in.model_dump(exclude_unset=True)

        # Handle attributes separately due to property setter
        if "attributes" in update_data:
            product.attributes = update_data.pop("attributes")

        for field, value in update_data.items():
            setattr(product, field, value)

        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product: Product) -> None:
        """Delete a product."""
        self.db.delete(product)
        self.db.commit()

    def count(self) -> int:
        """Count total products."""
        return self.db.query(Product).count()

    def validate_vendor_exists(self, vendor_id: str) -> bool:
        """Check if a vendor exists."""
        return self.db.query(Vendor).filter(Vendor.id == vendor_id).first() is not None

    def validate_category_exists(self, category_id: str) -> bool:
        """Check if a category exists."""
        return (
            self.db.query(Category).filter(Category.id == category_id).first()
            is not None
        )

    def enrich_with_names(self, product: Product) -> dict:
        """Add vendor_name and category_name to product data."""
        data = {
            "id": product.id,
            "sku": product.sku,
            "vendor_id": product.vendor_id,
            "category_id": product.category_id,
            "name": product.name,
            "product_family": product.product_family,
            "list_price": product.list_price_float,
            "cost_price": product.cost_price_float,
            "currency": product.currency,
            "lifecycle_status": product.lifecycle_status,
            "warranty_years": product.warranty_years,
            "attributes": product.attributes,
            "datasheet_url": product.datasheet_url,
            "image_url": product.image_url,
            "notes": product.notes,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "vendor_name": product.vendor.name if product.vendor else None,
            "category_name": product.category.name if product.category else None,
        }
        return data
