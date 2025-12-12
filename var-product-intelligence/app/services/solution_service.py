"""Solution service for managing solutions and generating BOMs."""

import math
from sqlalchemy.orm import Session

from app.models.solution import Solution, SolutionComponent
from app.models.vendor import Vendor
from app.models.product import Product
from app.schemas.solution import (
    BOMRequest,
    BOMResponse,
    BOMLineItem,
    SolutionCreate,
    SolutionSummary,
    SolutionResponse,
    SolutionComponentCreate,
)


class SolutionService:
    """Service for solution management and BOM generation."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def list_solutions(
        self,
        vendor_id: str | None = None,
        solution_type: str | None = None,
    ) -> list[SolutionSummary]:
        """List available solutions with optional filtering."""
        query = self.db.query(Solution)

        if vendor_id:
            query = query.filter(Solution.vendor_id == vendor_id)
        if solution_type:
            query = query.filter(Solution.solution_type == solution_type)

        solutions = query.all()

        result = []
        for sol in solutions:
            vendor = self.db.query(Vendor).filter(Vendor.id == sol.vendor_id).first()
            result.append(
                SolutionSummary(
                    id=sol.id,
                    name=sol.name,
                    vendor_id=sol.vendor_id,
                    vendor_name=vendor.name if vendor else None,
                    solution_type=sol.solution_type,
                    description=sol.description,
                    component_count=len(sol.components),
                )
            )

        return result

    def get_solution(self, solution_id: str) -> Solution | None:
        """Get a solution by ID."""
        return self.db.query(Solution).filter(Solution.id == solution_id).first()

    def get_solution_by_name(self, name: str, vendor_id: str) -> Solution | None:
        """Get a solution by name and vendor."""
        return (
            self.db.query(Solution)
            .filter(Solution.name == name, Solution.vendor_id == vendor_id)
            .first()
        )

    def create_solution(self, data: SolutionCreate) -> Solution:
        """Create a new solution with components."""
        solution = Solution(
            name=data.name,
            vendor_id=data.vendor_id,
            solution_type=data.solution_type,
            description=data.description,
            documentation_url=data.documentation_url,
        )
        if data.use_cases:
            solution.use_cases_list = data.use_cases

        self.db.add(solution)
        self.db.flush()  # Get the ID

        # Add components
        if data.components:
            for i, comp_data in enumerate(data.components):
                component = SolutionComponent(
                    solution_id=solution.id,
                    name=comp_data.name,
                    component_type=comp_data.component_type,
                    description=comp_data.description,
                    is_required=comp_data.is_required,
                    display_order=comp_data.display_order or i,
                    quantity_type=comp_data.quantity_type,
                    quantity_default=comp_data.quantity_default,
                    quantity_formula=comp_data.quantity_formula,
                    license_type=comp_data.license_type,
                    license_per_unit=comp_data.license_per_unit,
                    notes=comp_data.notes,
                )
                if comp_data.sizing_tiers:
                    component.sizing_tiers = comp_data.sizing_tiers
                if comp_data.product_options:
                    component.product_options = comp_data.product_options
                if comp_data.license_tiers:
                    component.license_tiers = comp_data.license_tiers
                if comp_data.license_term_months:
                    component.license_term_months = comp_data.license_term_months
                if comp_data.dependencies:
                    component.dependencies = comp_data.dependencies
                if comp_data.features:
                    component.features = comp_data.features

                self.db.add(component)

        self.db.commit()
        self.db.refresh(solution)
        return solution

    def generate_bom(self, request: BOMRequest) -> BOMResponse:
        """Generate a Bill of Materials for a solution.

        Args:
            request: BOM request with solution ID and parameters

        Returns:
            BOMResponse with line items and totals
        """
        solution = self.get_solution(request.solution_id)
        if not solution:
            raise ValueError(f"Solution not found: {request.solution_id}")

        vendor = self.db.query(Vendor).filter(Vendor.id == solution.vendor_id).first()

        line_items = []
        notes = []
        warnings = []
        hardware_total = 0.0
        licensing_total = 0.0

        # Sort components by display order
        components = sorted(solution.components, key=lambda c: c.display_order)

        for component in components:
            # Calculate quantity
            quantity = self._calculate_quantity(component, request)

            if quantity == 0 and not component.is_required:
                continue  # Skip optional components with zero quantity

            # Determine SKU and product info
            sku, product_name, unit_price = self._resolve_product(
                component, request, quantity
            )

            # Calculate extended price
            extended_price = None
            if unit_price is not None:
                extended_price = unit_price * quantity
                if component.component_type in ["license", "subscription"]:
                    licensing_total += extended_price
                else:
                    hardware_total += extended_price

            # Get license details
            license_tier = None
            license_term_months = None
            if component.component_type in ["license", "subscription"]:
                license_tier = request.license_tier
                if request.license_term_years:
                    license_term_months = request.license_term_years * 12
                elif component.license_term_months:
                    license_term_months = component.license_term_months[0]  # Default to first option

            # Build line item
            line_item = BOMLineItem(
                component_id=component.id,
                component_name=component.name,
                component_type=component.component_type,
                quantity=quantity,
                sku=sku,
                product_name=product_name,
                unit_price=unit_price,
                extended_price=extended_price,
                license_tier=license_tier,
                license_term_months=license_term_months,
                notes=component.notes,
                is_required=component.is_required,
            )
            line_items.append(line_item)

            # Add notes for special handling
            if component.notes:
                notes.append(f"{component.name}: {component.notes}")

        # Add solution-level notes
        if solution.use_cases_list:
            notes.append(f"Use cases: {', '.join(solution.use_cases_list)}")

        # Calculate grand total
        grand_total = None
        if hardware_total > 0 or licensing_total > 0:
            grand_total = hardware_total + licensing_total

        return BOMResponse(
            solution_id=solution.id,
            solution_name=solution.name,
            vendor_id=solution.vendor_id,
            vendor_name=vendor.name if vendor else None,
            parameters={
                "sites": request.sites,
                "devices": request.devices,
                "users": request.users,
                "license_tier": request.license_tier,
                "license_term_years": request.license_term_years,
                "ha_enabled": request.ha_enabled,
            },
            line_items=line_items,
            hardware_total=hardware_total if hardware_total > 0 else None,
            licensing_total=licensing_total if licensing_total > 0 else None,
            grand_total=grand_total,
            notes=notes,
            warnings=warnings,
        )

    def _calculate_quantity(
        self, component: SolutionComponent, request: BOMRequest
    ) -> int:
        """Calculate quantity for a component based on request parameters."""
        if component.quantity_type == "fixed":
            qty = component.quantity_default

            # Handle HA for controllers
            if (
                component.component_type == "controller"
                and request.ha_enabled
                and qty == 1
            ):
                qty = 2  # Add HA pair

            return qty

        elif component.quantity_type == "per_site":
            return request.sites or 0

        elif component.quantity_type == "per_device":
            return request.devices or request.sites or 0

        elif component.quantity_type == "per_user":
            return request.users or 0

        elif component.quantity_type == "calculated" and component.quantity_formula:
            # Simple formula evaluation
            formula = component.quantity_formula
            sites = request.sites or 0
            devices = request.devices or request.sites or 0
            users = request.users or 0

            # Replace variables
            formula = formula.replace("sites", str(sites))
            formula = formula.replace("devices", str(devices))
            formula = formula.replace("users", str(users))

            try:
                result = eval(formula)  # Safe for simple math expressions
                return max(1, math.ceil(result))
            except Exception:
                return component.quantity_default

        return component.quantity_default

    def _resolve_product(
        self,
        component: SolutionComponent,
        request: BOMRequest,
        quantity: int,
    ) -> tuple[str | None, str | None, float | None]:
        """Resolve the SKU, product name, and price for a component.

        Returns:
            Tuple of (sku, product_name, unit_price)
        """
        sku = None
        product_name = None
        unit_price = None

        # Check if user selected a specific product
        if request.product_selections and component.id in request.product_selections:
            sku = request.product_selections[component.id]
        # Check sizing tiers
        elif component.sizing_tiers:
            # Check if this is a license tier (has 'tier' key) vs scale-based tier (has max_* keys)
            first_tier = component.sizing_tiers[0] if component.sizing_tiers else {}

            if "tier" in first_tier and "term_years" in first_tier:
                # License tier selection based on tier name and term
                target_tier = request.license_tier or "essentials"
                target_term = request.license_term_years or 5

                for tier in component.sizing_tiers:
                    if tier.get("tier") == target_tier and tier.get("term_years") == target_term:
                        sku = tier.get("sku")
                        break

                # Fallback: find any matching tier regardless of term
                if not sku:
                    for tier in component.sizing_tiers:
                        if tier.get("tier") == target_tier:
                            sku = tier.get("sku")
                            break
            else:
                # Scale-based tier selection (controller sizing, etc.)
                scale_value = request.devices or request.sites or quantity
                for tier in component.sizing_tiers:
                    max_val = (
                        tier.get("max_aps") or
                        tier.get("max_devices") or
                        tier.get("max_sites") or
                        tier.get("max_users")
                    )
                    if max_val and scale_value <= max_val:
                        sku = tier.get("sku")
                        break
                # Use largest tier if none matched
                if not sku and component.sizing_tiers:
                    sku = component.sizing_tiers[-1].get("sku")
        # Use first product option
        elif component.product_options:
            sku = component.product_options[0]

        # Look up product in database for name and price
        if sku:
            product = (
                self.db.query(Product)
                .filter(Product.sku == sku)
                .first()
            )
            if product:
                product_name = product.name
                unit_price = product.list_price_float

        return sku, product_name, unit_price

    def delete_solution(self, solution_id: str) -> bool:
        """Delete a solution and its components."""
        solution = self.get_solution(solution_id)
        if not solution:
            return False

        self.db.delete(solution)
        self.db.commit()
        return True
