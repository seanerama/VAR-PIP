"""Category database model."""

import json
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship

from app.models.database import Base


class Category(Base):
    """Category model representing product categories with attribute schemas."""

    __tablename__ = "categories"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # Store JSON schema as text for SQLite compatibility
    _attribute_schema = Column("attribute_schema", Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products = relationship("Product", back_populates="category")

    @property
    def attribute_schema(self) -> dict | None:
        """Get attribute schema as dict."""
        if self._attribute_schema:
            return json.loads(self._attribute_schema)
        return None

    @attribute_schema.setter
    def attribute_schema(self, value: dict | None):
        """Set attribute schema from dict."""
        if value is not None:
            self._attribute_schema = json.dumps(value)
        else:
            self._attribute_schema = None

    def __repr__(self):
        return f"<Category(id='{self.id}', name='{self.name}')>"
