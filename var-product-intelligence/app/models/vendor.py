"""Vendor database model."""

from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship

from app.models.database import Base


class Vendor(Base):
    """Vendor model representing equipment manufacturers."""

    __tablename__ = "vendors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    partner_portal_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products = relationship("Product", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor(id='{self.id}', name='{self.name}')>"
