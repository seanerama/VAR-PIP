"""Product database model."""

import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Product(Base):
    """Product model representing network equipment products."""

    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    sku = Column(String, nullable=False, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    product_family = Column(String, nullable=True)
    list_price = Column(Numeric(10, 2), nullable=True)
    cost_price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String, default="USD")
    lifecycle_status = Column(String, default="active")  # active, end_of_sale, end_of_life
    warranty_years = Column(Integer, nullable=True)
    # Store JSON attributes as text for SQLite compatibility
    _attributes = Column("attributes", Text, nullable=True)
    datasheet_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vendor = relationship("Vendor", back_populates="products")
    category = relationship("Category", back_populates="products")

    @property
    def attributes(self) -> dict | None:
        """Get attributes as dict."""
        if self._attributes:
            return json.loads(self._attributes)
        return None

    @attributes.setter
    def attributes(self, value: dict | None):
        """Set attributes from dict."""
        if value is not None:
            self._attributes = json.dumps(value)
        else:
            self._attributes = None

    @property
    def list_price_float(self) -> float | None:
        """Get list price as float."""
        if self.list_price is not None:
            return float(self.list_price)
        return None

    @property
    def cost_price_float(self) -> float | None:
        """Get cost price as float."""
        if self.cost_price is not None:
            return float(self.cost_price)
        return None

    def __repr__(self):
        return f"<Product(id='{self.id}', sku='{self.sku}', name='{self.name}')>"
