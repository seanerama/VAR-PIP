"""Solution database models for BOM generation."""

import json
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Solution(Base):
    """Solution template representing a complete vendor solution."""

    __tablename__ = "solutions"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    name = Column(String, nullable=False)  # "Cisco SD-WAN"
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    solution_type = Column(String, nullable=False, index=True)  # "sdwan", "wireless", "security"
    description = Column(Text, nullable=True)
    use_cases = Column(Text, nullable=True)  # JSON array of use case strings
    documentation_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vendor = relationship("Vendor", back_populates="solutions")
    components = relationship("SolutionComponent", back_populates="solution", cascade="all, delete-orphan")

    @property
    def use_cases_list(self) -> list[str]:
        """Get use cases as list."""
        if self.use_cases:
            return json.loads(self.use_cases)
        return []

    @use_cases_list.setter
    def use_cases_list(self, value: list[str]):
        """Set use cases from list."""
        if value:
            self.use_cases = json.dumps(value)
        else:
            self.use_cases = None

    def __repr__(self):
        return f"<Solution(id='{self.id}', name='{self.name}')>"


class SolutionComponent(Base):
    """Component within a solution (hardware, software, or license)."""

    __tablename__ = "solution_components"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    solution_id = Column(String, ForeignKey("solutions.id"), nullable=False, index=True)
    name = Column(String, nullable=False)  # "vManage Controller"
    component_type = Column(String, nullable=False)  # "controller", "edge", "license", "subscription", "software"
    description = Column(Text, nullable=True)
    is_required = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)  # For ordering in BOM output

    # Quantity calculation
    quantity_type = Column(String, default="fixed")  # "fixed", "per_site", "per_device", "per_user", "calculated"
    quantity_default = Column(Integer, default=1)
    quantity_formula = Column(String, nullable=True)  # For calculated: "sites * 2", "devices / 6000"

    # Sizing tiers (JSON) - for components that scale
    # Example: [{"max_devices": 1000, "sku": "VMANAGE-S"}, {"max_devices": 5000, "sku": "VMANAGE-M"}]
    _sizing_tiers = Column("sizing_tiers", Text, nullable=True)

    # Product options (JSON array of SKUs or product family references)
    # Example: ["C8300-1N1S-4T2X", "C8300-2N2S-4T2X", "ISR4331"]
    _product_options = Column("product_options", Text, nullable=True)

    # License details
    license_type = Column(String, nullable=True)  # "subscription", "perpetual", "term"
    _license_tiers = Column("license_tiers", Text, nullable=True)  # JSON: ["essentials", "advantage", "premier"]
    _license_term_months = Column("license_term_months", Text, nullable=True)  # JSON: [12, 36, 60]
    license_per_unit = Column(String, nullable=True)  # "device", "ap", "user", "site"

    # Dependencies (JSON array of component IDs this requires)
    _dependencies = Column("dependencies", Text, nullable=True)

    # Additional metadata
    notes = Column(Text, nullable=True)
    _features = Column("features", Text, nullable=True)  # JSON array of feature strings

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    solution = relationship("Solution", back_populates="components")

    @property
    def sizing_tiers(self) -> list[dict] | None:
        """Get sizing tiers as list of dicts."""
        if self._sizing_tiers:
            return json.loads(self._sizing_tiers)
        return None

    @sizing_tiers.setter
    def sizing_tiers(self, value: list[dict] | None):
        """Set sizing tiers from list of dicts."""
        if value:
            self._sizing_tiers = json.dumps(value)
        else:
            self._sizing_tiers = None

    @property
    def product_options(self) -> list[str] | None:
        """Get product options as list."""
        if self._product_options:
            return json.loads(self._product_options)
        return None

    @product_options.setter
    def product_options(self, value: list[str] | None):
        """Set product options from list."""
        if value:
            self._product_options = json.dumps(value)
        else:
            self._product_options = None

    @property
    def license_tiers(self) -> list[str] | None:
        """Get license tiers as list."""
        if self._license_tiers:
            return json.loads(self._license_tiers)
        return None

    @license_tiers.setter
    def license_tiers(self, value: list[str] | None):
        """Set license tiers from list."""
        if value:
            self._license_tiers = json.dumps(value)
        else:
            self._license_tiers = None

    @property
    def license_term_months(self) -> list[int] | None:
        """Get license term options as list."""
        if self._license_term_months:
            return json.loads(self._license_term_months)
        return None

    @license_term_months.setter
    def license_term_months(self, value: list[int] | None):
        """Set license term options from list."""
        if value:
            self._license_term_months = json.dumps(value)
        else:
            self._license_term_months = None

    @property
    def dependencies(self) -> list[str] | None:
        """Get dependencies as list of component IDs."""
        if self._dependencies:
            return json.loads(self._dependencies)
        return None

    @dependencies.setter
    def dependencies(self, value: list[str] | None):
        """Set dependencies from list."""
        if value:
            self._dependencies = json.dumps(value)
        else:
            self._dependencies = None

    @property
    def features(self) -> list[str] | None:
        """Get features as list."""
        if self._features:
            return json.loads(self._features)
        return None

    @features.setter
    def features(self, value: list[str] | None):
        """Set features from list."""
        if value:
            self._features = json.dumps(value)
        else:
            self._features = None

    def __repr__(self):
        return f"<SolutionComponent(id='{self.id}', name='{self.name}', type='{self.component_type}')>"
