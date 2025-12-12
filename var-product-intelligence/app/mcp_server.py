"""FastMCP server exposing VAR Product Intelligence Platform APIs as LLM tools."""

import json
from typing import Any

from fastmcp import FastMCP

from app.config import settings
from app.models.database import get_db
from app.models.product import Product
from app.models.vendor import Vendor
from app.models.category import Category
from app.services.product_service import ProductService
from app.services.filter_service import FilterService
from app.services.extraction_service import ExtractionService
from app.services.comparison_service import ComparisonService
from app.services.solution_service import SolutionService
from app.schemas.extract import UrlExtractionRequest, BatchUrlExtractionRequest
from app.schemas.compare import CompareRequest
from app.schemas.solution import BOMRequest, SolutionCreate, SolutionComponentCreate
from app.schemas.price_import import (
    PriceImportRequest,
    PriceExportRequest,
    ColumnMapping,
)
from app.services.price_import_service import PriceImportService, PRESET_MAPPINGS
from app.services.cisco_pricing_service import CiscoPricingService
from app.schemas.cisco_pricing import (
    CiscoPriceSyncRequest,
    CiscoPriceLookupRequest,
)

# Initialize FastMCP server
mcp = FastMCP(
    "VAR Product Intelligence",
    instructions="Tools for managing and comparing network equipment products for Value-Added Resellers. Use these tools to list products, extract product data from datasheets, compare products, and manage vendors.",
)


def get_db_session():
    """Get a database session."""
    return next(get_db())


# ============== Product Tools ==============

@mcp.tool()
def list_products(
    category_id: str | None = None,
    vendor_id: str | None = None,
    search: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    lifecycle_status: str | None = None,
    limit: int = 20,
) -> str:
    """List products with optional filtering.

    Args:
        category_id: Filter by category (e.g., 'wireless_access_points')
        vendor_id: Filter by vendor (e.g., 'cisco', 'aruba')
        search: Search in product name, SKU, or product family
        min_price: Minimum list price
        max_price: Maximum list price
        lifecycle_status: Filter by status ('active', 'end_of_sale', 'end_of_life')
        limit: Maximum number of products to return (default 20)

    Returns:
        JSON string with list of products and total count
    """
    db = get_db_session()
    try:
        filter_service = FilterService(db)

        vendors = [vendor_id] if vendor_id else None

        query = filter_service.build_query(
            category=category_id,
            vendors=vendors,
            lifecycle_status=lifecycle_status,
            min_price=min_price,
            max_price=max_price,
            search=search,
        )
        products, total = filter_service.execute_with_pagination(query, skip=0, limit=limit)

        result = {
            "total": total,
            "products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "vendor_id": p.vendor_id,
                    "category_id": p.category_id,
                    "product_family": p.product_family,
                    "list_price": p.list_price,
                    "lifecycle_status": p.lifecycle_status,
                    "attributes": p.attributes,
                }
                for p in products
            ],
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_product(product_id: str) -> str:
    """Get detailed information about a specific product.

    Args:
        product_id: The UUID of the product

    Returns:
        JSON string with product details or error message
    """
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            return json.dumps({"error": f"Product with ID '{product_id}' not found"})

        result = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "vendor_id": product.vendor_id,
            "category_id": product.category_id,
            "product_family": product.product_family,
            "list_price": product.list_price,
            "cost_price": product.cost_price,
            "currency": product.currency,
            "lifecycle_status": product.lifecycle_status,
            "warranty_years": product.warranty_years,
            "attributes": product.attributes,
            "datasheet_url": product.datasheet_url,
            "image_url": product.image_url,
            "notes": product.notes,
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def search_products_by_attribute(
    category_id: str,
    attribute_name: str,
    attribute_value: str,
    limit: int = 20,
) -> str:
    """Search products by a specific attribute value.

    Args:
        category_id: Category to search in (e.g., 'wireless_access_points')
        attribute_name: Name of the attribute (e.g., 'wifi_generation', 'form_factor')
        attribute_value: Value to search for (e.g., 'wifi7', 'outdoor')
        limit: Maximum number of products to return

    Returns:
        JSON string with matching products
    """
    db = get_db_session()
    try:
        filter_service = FilterService(db)

        attribute_filters = {attribute_name: attribute_value}

        query = filter_service.build_query(
            category=category_id,
            attribute_filters=attribute_filters,
        )
        products, total = filter_service.execute_with_pagination(query, skip=0, limit=limit)

        result = {
            "total": total,
            "filter_applied": {attribute_name: attribute_value},
            "products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "vendor_id": p.vendor_id,
                    "list_price": p.list_price,
                    "attributes": p.attributes,
                }
                for p in products
            ],
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


# ============== Extraction Tools ==============

@mcp.tool()
def extract_product_from_url(
    url: str,
    category_id: str,
    vendor_id: str,
    save_product: bool = True,
    extract_all_products: bool = False,
) -> str:
    """Extract product data from a datasheet URL using AI.

    This tool fetches a URL and extracts structured product information.
    If the URL is an HTML page with PDF links, it returns those links.
    If it's a direct PDF or HTML with specs, it extracts the product data.

    Args:
        url: URL to a product datasheet (PDF) or product page
        category_id: Category for the product (e.g., 'wireless_access_points')
        vendor_id: Vendor ID (e.g., 'cisco', 'aruba', 'juniper')
        save_product: Whether to automatically save the extracted product (default True)
        extract_all_products: If True, extract ALL products from family datasheets separately
                              instead of merging into one entry (default False)

    Returns:
        JSON string with extraction results, including:
        - source_type: 'pdf', 'html', or 'pdf_listing'
        - extracted_product: The extracted product data (if single product mode)
        - product_saved: Whether the product was saved to database
        - saved_product_id: ID of saved product (if saved)
        - pdf_links_found: List of PDF links (if source_type is 'pdf_listing')
        - multi_product_mode: True if extract_all_products was enabled
        - products_found: Number of products found (in multi-product mode)
        - products_saved: Number of products saved (in multi-product mode)
        - product_results: List of individual product results (in multi-product mode)
    """
    db = get_db_session()
    try:
        service = ExtractionService(db)

        request = UrlExtractionRequest(
            url=url,
            category_id=category_id,
            vendor_id=vendor_id,
            save_product=save_product,
            extract_all_products=extract_all_products,
        )

        result = service.extract_from_url(request)

        # Convert to dict for JSON serialization
        response = {
            "extraction_id": result.extraction_id,
            "source_type": result.source_type,
            "source_url": result.source_url,
            "status": result.status,
            "confidence_score": result.confidence_score,
            "warnings": result.warnings,
            "vendor_created": result.vendor_created,
            "product_saved": result.product_saved,
            "saved_product_id": result.saved_product_id,
        }

        # Handle multi-product mode response
        if result.multi_product_mode:
            response["multi_product_mode"] = True
            response["products_found"] = result.products_found
            response["products_saved"] = result.products_saved
            response["product_results"] = [
                {
                    "sku": pr.sku,
                    "name": pr.name,
                    "product_saved": pr.product_saved,
                    "saved_product_id": pr.saved_product_id,
                    "error": pr.error,
                }
                for pr in result.product_results
            ]
        elif result.extracted_product:
            response["extracted_product"] = {
                "sku": result.extracted_product.sku,
                "name": result.extracted_product.name,
                "product_family": result.extracted_product.product_family,
                "attributes": {
                    k: {"value": v.value, "confidence": v.confidence}
                    for k, v in result.extracted_product.attributes.items()
                },
            }

        if result.pdf_links_found:
            response["pdf_links_found"] = [
                {"url": link.url, "title": link.title}
                for link in result.pdf_links_found
            ]

        return json.dumps(response, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def extract_products_batch(
    pdf_urls: list[str],
    category_id: str,
    vendor_id: str,
    save_products: bool = True,
) -> str:
    """Extract product data from multiple PDF URLs.

    Use this after getting a list of PDF links from extract_product_from_url.

    Args:
        pdf_urls: List of direct PDF URLs to extract from
        category_id: Category for the products
        vendor_id: Vendor ID
        save_products: Whether to automatically save extracted products

    Returns:
        JSON string with batch extraction results
    """
    db = get_db_session()
    try:
        service = ExtractionService(db)

        request = BatchUrlExtractionRequest(
            pdf_urls=pdf_urls,
            category_id=category_id,
            vendor_id=vendor_id,
            save_product=save_products,
        )

        result = service.extract_batch_from_urls(request)

        response = {
            "total": result.total,
            "successful": result.successful,
            "failed": result.failed,
            "vendor_created": result.vendor_created,
            "results": [],
        }

        for r in result.results:
            item = {
                "url": r.url,
                "success": r.success,
                "status": r.status,
                "confidence_score": r.confidence_score,
                "product_saved": r.product_saved,
                "saved_product_id": r.saved_product_id,
                "error": r.error,
            }
            if r.extracted_product:
                item["extracted_sku"] = r.extracted_product.sku
                item["extracted_name"] = r.extracted_product.name
            response["results"].append(item)

        return json.dumps(response, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# ============== Vendor Tools ==============

@mcp.tool()
def list_vendors() -> str:
    """List all vendors in the system.

    Returns:
        JSON string with list of vendors
    """
    db = get_db_session()
    try:
        vendors = db.query(Vendor).all()

        result = [
            {
                "id": v.id,
                "name": v.name,
                "website": v.website,
            }
            for v in vendors
        ]
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def create_vendor(
    vendor_id: str,
    name: str,
    website: str | None = None,
) -> str:
    """Create a new vendor.

    Args:
        vendor_id: Unique identifier for the vendor (e.g., 'cisco', 'aruba')
        name: Display name of the vendor
        website: Vendor's website URL (optional)

    Returns:
        JSON string with created vendor or error
    """
    db = get_db_session()
    try:
        existing = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if existing:
            return json.dumps({"error": f"Vendor '{vendor_id}' already exists"})

        vendor = Vendor(id=vendor_id, name=name, website=website)
        db.add(vendor)
        db.commit()

        return json.dumps({
            "success": True,
            "vendor": {"id": vendor.id, "name": vendor.name, "website": vendor.website},
        })
    finally:
        db.close()


# ============== Category Tools ==============

@mcp.tool()
def list_categories() -> str:
    """List all product categories and their attribute schemas.

    Returns:
        JSON string with list of categories and their schemas
    """
    db = get_db_session()
    try:
        categories = db.query(Category).all()

        result = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "attribute_schema": c.attribute_schema,
            }
            for c in categories
        ]
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_category_attributes(category_id: str) -> str:
    """Get the attribute schema for a specific category.

    This shows what attributes are available for filtering/searching products
    in this category, including their types and allowed values.

    Args:
        category_id: The category ID (e.g., 'wireless_access_points')

    Returns:
        JSON string with attribute schema details
    """
    db = get_db_session()
    try:
        category = db.query(Category).filter(Category.id == category_id).first()

        if not category:
            return json.dumps({"error": f"Category '{category_id}' not found"})

        schema = category.attribute_schema or {}
        properties = schema.get("properties", {})

        attributes = []
        for attr_name, attr_def in properties.items():
            attr_info = {
                "name": attr_name,
                "type": attr_def.get("type"),
                "description": attr_def.get("description"),
            }
            if "enum" in attr_def:
                attr_info["allowed_values"] = attr_def["enum"]
            if attr_def.get("type") == "array" and "items" in attr_def:
                attr_info["item_values"] = attr_def["items"].get("enum")
            attributes.append(attr_info)

        return json.dumps({
            "category_id": category.id,
            "category_name": category.name,
            "attributes": attributes,
        }, indent=2)
    finally:
        db.close()


# ============== Comparison Tools ==============

@mcp.tool()
def compare_products(
    product_ids: list[str],
    title: str | None = None,
    include_pricing: bool = True,
) -> str:
    """Generate a comparison between 2-10 products.

    Creates a PDF comparison document showing products side-by-side.
    All products must be in the same category.

    Args:
        product_ids: List of product IDs to compare (2-10 products)
        title: Optional title for the comparison document
        include_pricing: Whether to include pricing information (default True)

    Returns:
        JSON string with comparison result including PDF download URL
    """
    db = get_db_session()
    try:
        service = ComparisonService(db)

        request = CompareRequest(
            product_ids=product_ids,
            title=title,
            include_pricing=include_pricing,
        )

        result = service.create_comparison(request)

        return json.dumps({
            "comparison_id": result.comparison_id,
            "pdf_url": result.pdf_url,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None,
            "product_count": result.product_count,
            "category": result.category,
            "message": f"Comparison PDF generated. Download from: {result.pdf_url}",
        }, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# ============== Utility Tools ==============

@mcp.tool()
def get_product_by_sku(sku: str) -> str:
    """Find a product by its SKU.

    Args:
        sku: The product SKU (e.g., 'CW9179F')

    Returns:
        JSON string with product details or error
    """
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.sku == sku).first()

        if not product:
            return json.dumps({"error": f"Product with SKU '{sku}' not found"})

        result = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "vendor_id": product.vendor_id,
            "category_id": product.category_id,
            "product_family": product.product_family,
            "list_price": product.list_price,
            "lifecycle_status": product.lifecycle_status,
            "attributes": product.attributes,
            "datasheet_url": product.datasheet_url,
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def delete_product(product_id: str) -> str:
    """Delete a product from the database.

    Args:
        product_id: The UUID of the product to delete

    Returns:
        JSON string with success or error message
    """
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            return json.dumps({"error": f"Product with ID '{product_id}' not found"})

        sku = product.sku
        name = product.name
        db.delete(product)
        db.commit()

        return json.dumps({
            "success": True,
            "message": f"Product '{name}' (SKU: {sku}) deleted successfully",
        })
    finally:
        db.close()


@mcp.tool()
def update_product_price(
    product_id: str,
    list_price: float | None = None,
    cost_price: float | None = None,
) -> str:
    """Update the pricing for a product.

    Args:
        product_id: The UUID of the product
        list_price: New list price (optional)
        cost_price: New cost price (optional)

    Returns:
        JSON string with updated product or error
    """
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            return json.dumps({"error": f"Product with ID '{product_id}' not found"})

        if list_price is not None:
            product.list_price = list_price
        if cost_price is not None:
            product.cost_price = cost_price

        db.commit()

        return json.dumps({
            "success": True,
            "product": {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "list_price": product.list_price,
                "cost_price": product.cost_price,
            },
        })
    finally:
        db.close()


# ============== Solution Tools ==============

@mcp.tool()
def list_solutions(
    vendor_id: str | None = None,
    solution_type: str | None = None,
) -> str:
    """List available solution templates.

    Solution templates define the components needed to implement a complete
    vendor solution (e.g., Cisco SD-WAN, Aruba Wireless).

    Args:
        vendor_id: Filter by vendor (e.g., 'cisco', 'aruba')
        solution_type: Filter by type (e.g., 'sdwan', 'wireless', 'security')

    Returns:
        JSON string with list of solutions
    """
    db = get_db_session()
    try:
        service = SolutionService(db)
        solutions = service.list_solutions(vendor_id=vendor_id, solution_type=solution_type)

        result = {
            "total": len(solutions),
            "solutions": [
                {
                    "id": s.id,
                    "name": s.name,
                    "vendor_id": s.vendor_id,
                    "vendor_name": s.vendor_name,
                    "solution_type": s.solution_type,
                    "description": s.description,
                    "component_count": s.component_count,
                }
                for s in solutions
            ],
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_solution(solution_id: str) -> str:
    """Get detailed information about a solution template.

    Returns the solution with all its components, including sizing tiers,
    product options, and licensing details.

    Args:
        solution_id: The UUID of the solution

    Returns:
        JSON string with solution details and components
    """
    db = get_db_session()
    try:
        service = SolutionService(db)
        solution = service.get_solution(solution_id)

        if not solution:
            return json.dumps({"error": f"Solution with ID '{solution_id}' not found"})

        result = {
            "id": solution.id,
            "name": solution.name,
            "vendor_id": solution.vendor_id,
            "solution_type": solution.solution_type,
            "description": solution.description,
            "use_cases": solution.use_cases_list,
            "documentation_url": solution.documentation_url,
            "components": [
                {
                    "id": c.id,
                    "name": c.name,
                    "component_type": c.component_type,
                    "description": c.description,
                    "is_required": c.is_required,
                    "display_order": c.display_order,
                    "quantity_type": c.quantity_type,
                    "quantity_default": c.quantity_default,
                    "quantity_formula": c.quantity_formula,
                    "sizing_tiers": c.sizing_tiers,
                    "product_options": c.product_options,
                    "license_type": c.license_type,
                    "license_tiers": c.license_tiers,
                    "license_term_months": c.license_term_months,
                    "license_per_unit": c.license_per_unit,
                    "notes": c.notes,
                    "features": c.features,
                }
                for c in sorted(solution.components, key=lambda x: x.display_order)
            ],
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def generate_solution_bom(
    solution_id: str,
    sites: int | None = None,
    devices: int | None = None,
    users: int | None = None,
    license_tier: str | None = None,
    license_term_years: int | None = None,
    ha_enabled: bool = True,
    product_selections: dict[str, str] | None = None,
) -> str:
    """Generate a Bill of Materials (BOM) for a solution.

    Creates a detailed BOM with quantities, SKUs, and pricing based on
    the solution template and provided sizing parameters.

    Args:
        solution_id: The UUID of the solution template
        sites: Number of sites (for SD-WAN, wireless deployments)
        devices: Number of devices/endpoints (APs, edge routers, etc.)
        users: Number of users (for user-based licensing)
        license_tier: License tier (e.g., 'essentials', 'advantage', 'premier')
        license_term_years: License term in years (1-7)
        ha_enabled: Whether to include high availability (default True)
        product_selections: Override specific components with SKUs (component_id -> SKU)

    Returns:
        JSON string with BOM line items and totals
    """
    db = get_db_session()
    try:
        service = SolutionService(db)

        request = BOMRequest(
            solution_id=solution_id,
            sites=sites,
            devices=devices,
            users=users,
            license_tier=license_tier,
            license_term_years=license_term_years,
            ha_enabled=ha_enabled,
            product_selections=product_selections,
        )

        bom = service.generate_bom(request)

        result = {
            "solution_id": bom.solution_id,
            "solution_name": bom.solution_name,
            "vendor_id": bom.vendor_id,
            "vendor_name": bom.vendor_name,
            "parameters": bom.parameters,
            "line_items": [
                {
                    "component_id": item.component_id,
                    "component_name": item.component_name,
                    "component_type": item.component_type,
                    "quantity": item.quantity,
                    "sku": item.sku,
                    "product_name": item.product_name,
                    "unit_price": item.unit_price,
                    "extended_price": item.extended_price,
                    "license_tier": item.license_tier,
                    "license_term_months": item.license_term_months,
                    "notes": item.notes,
                    "is_required": item.is_required,
                }
                for item in bom.line_items
            ],
            "hardware_total": bom.hardware_total,
            "licensing_total": bom.licensing_total,
            "grand_total": bom.grand_total,
            "notes": bom.notes,
            "warnings": bom.warnings,
        }
        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def create_solution(
    name: str,
    vendor_id: str,
    solution_type: str,
    description: str | None = None,
    use_cases: list[str] | None = None,
    documentation_url: str | None = None,
    components: list[dict] | None = None,
) -> str:
    """Create a new solution template.

    Defines a complete vendor solution with its components for BOM generation.

    Args:
        name: Solution name (e.g., 'Cisco SD-WAN')
        vendor_id: Vendor ID (e.g., 'cisco')
        solution_type: Solution type ('sdwan', 'wireless', 'security', 'switching')
        description: Solution description
        use_cases: List of use case descriptions
        documentation_url: Link to vendor documentation
        components: List of component definitions, each with:
            - name: Component name
            - component_type: 'controller', 'edge', 'license', 'subscription', 'software', 'optional'
            - description: Component description
            - is_required: Whether required (default True)
            - display_order: Order in BOM output
            - quantity_type: 'fixed', 'per_site', 'per_device', 'per_user', 'calculated'
            - quantity_default: Default quantity
            - quantity_formula: Formula for calculated quantities
            - sizing_tiers: List of {max_devices/sites: X, sku: 'SKU'} for scaling
            - product_options: List of SKU options
            - license_type: 'subscription', 'perpetual', 'term'
            - license_tiers: Available tiers like ['essentials', 'advantage']
            - license_term_months: Available terms like [12, 36, 60]
            - license_per_unit: 'device', 'user', 'site'
            - notes: Additional notes
            - features: Feature list

    Returns:
        JSON string with created solution
    """
    db = get_db_session()
    try:
        service = SolutionService(db)

        # Check if solution already exists
        existing = service.get_solution_by_name(name, vendor_id)
        if existing:
            return json.dumps({"error": f"Solution '{name}' already exists for vendor '{vendor_id}'"})

        # Build component list
        component_creates = []
        if components:
            for comp in components:
                component_creates.append(SolutionComponentCreate(**comp))

        data = SolutionCreate(
            name=name,
            vendor_id=vendor_id,
            solution_type=solution_type,
            description=description,
            use_cases=use_cases,
            documentation_url=documentation_url,
            components=component_creates,
        )

        solution = service.create_solution(data)

        return json.dumps({
            "success": True,
            "solution": {
                "id": solution.id,
                "name": solution.name,
                "vendor_id": solution.vendor_id,
                "solution_type": solution.solution_type,
                "component_count": len(solution.components),
            },
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def delete_solution(solution_id: str) -> str:
    """Delete a solution template and all its components.

    Args:
        solution_id: The UUID of the solution to delete

    Returns:
        JSON string with success or error message
    """
    db = get_db_session()
    try:
        service = SolutionService(db)
        solution = service.get_solution(solution_id)

        if not solution:
            return json.dumps({"error": f"Solution with ID '{solution_id}' not found"})

        name = solution.name
        service.delete_solution(solution_id)

        return json.dumps({
            "success": True,
            "message": f"Solution '{name}' deleted successfully",
        })
    finally:
        db.close()


# ============== Price Import/Export Tools ==============

@mcp.tool()
def import_prices(
    file_path: str,
    price_type: str = "list",
    format: str = "auto",
    vendor_id: str | None = None,
    category_id: str | None = None,
    create_missing: bool = False,
    update_existing: bool = True,
    dry_run: bool = False,
    custom_sku_column: str | None = None,
    custom_price_column: str | None = None,
    custom_name_column: str | None = None,
    custom_vendor_column: str | None = None,
) -> str:
    """Import prices from a CSV file.

    Bulk load pricing data from distributor CSV exports (Ingram Micro, TD SYNNEX, D&H)
    or custom CSV files. Auto-detects column mappings for common formats.

    Args:
        file_path: Path to the CSV file to import
        price_type: Type of price to import ('list' or 'cost')
        format: CSV format preset or detection mode:
            - 'auto': Auto-detect format (default)
            - 'ingram': Ingram Micro format
            - 'synnex': TD SYNNEX format
            - 'dnh': D&H format
            - 'generic': Simple sku,name,price,vendor columns
            - 'custom': Use custom column mappings
        vendor_id: Override vendor for all imported prices
        category_id: Category for newly created products
        create_missing: Create products that don't exist in database (default False)
        update_existing: Update prices for existing products (default True)
        dry_run: Preview changes without saving (default False)
        custom_sku_column: Column name for SKU (required if format='custom')
        custom_price_column: Column name for price (required if format='custom')
        custom_name_column: Column name for product name (optional)
        custom_vendor_column: Column name for vendor (optional)

    Returns:
        JSON string with import results including:
        - total_rows: Number of rows in CSV
        - matched: Products matched in database
        - created: New products created
        - updated: Products with updated prices
        - skipped: Rows skipped (invalid data, etc.)
        - errors: Number of errors
        - items: Details for each row processed
    """
    db = get_db_session()
    try:
        service = PriceImportService(db)

        # Build custom mapping if provided
        custom_mapping = None
        if format == "custom" or custom_sku_column or custom_price_column:
            if not custom_sku_column or not custom_price_column:
                return json.dumps({
                    "error": "Custom column mapping requires both custom_sku_column and custom_price_column"
                })
            custom_mapping = ColumnMapping(
                sku_column=custom_sku_column,
                price_column=custom_price_column,
                name_column=custom_name_column,
                vendor_column=custom_vendor_column,
            )
            format = "custom"

        request = PriceImportRequest(
            file_path=file_path,
            price_type=price_type,
            format=format,
            custom_mapping=custom_mapping,
            vendor_id=vendor_id,
            category_id=category_id,
            create_missing=create_missing,
            update_existing=update_existing,
            dry_run=dry_run,
        )

        result = service.import_prices(request)

        response = {
            "success": result.success,
            "file_path": result.file_path,
            "format_detected": result.format_detected,
            "price_type": result.price_type,
            "dry_run": result.dry_run,
            "total_rows": result.total_rows,
            "matched": result.matched,
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "errors": result.errors,
            "warnings": result.warnings,
        }

        # Include item details (limited to first 50 for readability)
        if result.items:
            response["items"] = [
                {
                    "sku": item.sku,
                    "name": item.name,
                    "old_price": item.old_price,
                    "new_price": item.new_price,
                    "action": item.action,
                    "message": item.message,
                }
                for item in result.items[:50]
            ]
            if len(result.items) > 50:
                response["items_truncated"] = True
                response["total_items"] = len(result.items)

        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def export_prices(
    file_path: str,
    vendor_id: str | None = None,
    category_id: str | None = None,
    include_cost: bool = False,
    format: str = "generic",
) -> str:
    """Export prices to a CSV file.

    Export current product pricing to a CSV file for backup, analysis,
    or transfer to other systems.

    Args:
        file_path: Output file path for the CSV
        vendor_id: Filter by vendor (optional)
        category_id: Filter by category (optional)
        include_cost: Include cost prices in output (default False)
        format: Output format:
            - 'generic': Basic columns (sku, name, vendor_id, list_price)
            - 'detailed': Full columns including cost, family, lifecycle, etc.

    Returns:
        JSON string with export results including:
        - total_products: Number of products exported
        - with_prices: Products that have list prices
        - without_prices: Products missing list prices
    """
    db = get_db_session()
    try:
        service = PriceImportService(db)

        request = PriceExportRequest(
            file_path=file_path,
            vendor_id=vendor_id,
            category_id=category_id,
            include_cost=include_cost,
            format=format,
        )

        result = service.export_prices(request)

        return json.dumps({
            "success": result.success,
            "file_path": result.file_path,
            "total_products": result.total_products,
            "with_prices": result.with_prices,
            "without_prices": result.without_prices,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# ============== Cisco Pricing Tools ==============

@mcp.tool()
def sync_cisco_prices(
    skus: list[str] | None = None,
    price_list: str = "GLUS",
    batch_size: int = 50,
    delay_between_batches: float = 2.0,
    update_eol_info: bool = False,
    dry_run: bool = False,
) -> str:
    """Sync prices from Cisco Commerce Catalog API to database.

    Fetches current list prices from Cisco's official pricing API and
    updates the VAR-PIP database. Uses rate limiting to avoid API throttling.

    Args:
        skus: Specific SKUs to sync. If None, syncs ALL Cisco products in database.
        price_list: Cisco price list code:
            - GLUS: US pricing (default)
            - GLEMEA: EMEA pricing
            - GLEURO: Euro pricing
            - GLCA: Canadian pricing
            - GLGB: UK pricing in GBP
        batch_size: SKUs per API request (1-200, default 50). Lower = safer for rate limits.
        delay_between_batches: Seconds between batches (0.5-30, default 2.0)
        update_eol_info: Also fetch End-of-Life dates (default False)
        dry_run: Preview changes without saving (default False)

    Returns:
        JSON string with sync results including updated/unchanged/not_found counts

    Example:
        >>> sync_cisco_prices(skus=["C9300-24T-E", "C9300-48T-E"])
        >>> sync_cisco_prices(dry_run=True)  # Preview all Cisco products
    """
    db = get_db_session()
    try:
        service = CiscoPricingService(db)

        request = CiscoPriceSyncRequest(
            skus=skus,
            price_list=price_list,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches,
            update_eol_info=update_eol_info,
            dry_run=dry_run,
        )

        result = service.sync_prices_sync(request)

        response = {
            "success": result.success,
            "price_list": result.price_list,
            "dry_run": result.dry_run,
            "total_requested": result.total_requested,
            "found": result.found,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "not_found": result.not_found,
            "errors": result.errors,
            "duration_seconds": result.duration_seconds,
            "warnings": result.warnings,
        }

        # Include sample of items (first 20)
        if result.items:
            response["items"] = [
                {
                    "sku": item.sku,
                    "old_price": item.old_price,
                    "new_price": item.new_price,
                    "currency": item.currency,
                    "action": item.action,
                    "message": item.message,
                }
                for item in result.items[:20]
            ]
            if len(result.items) > 20:
                response["items_truncated"] = True
                response["total_items"] = len(result.items)

        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def lookup_cisco_prices(
    skus: list[str],
    price_list: str = "GLUS",
    include_availability: bool = False,
    include_eol: bool = False,
) -> str:
    """Look up real-time Cisco prices without saving to database.

    Use this for quick price checks or quoting. Does NOT update the database.
    For bulk syncing, use sync_cisco_prices instead.

    Args:
        skus: List of Cisco SKUs to look up (max 50)
        price_list: Price list code (default GLUS for US pricing)
        include_availability: Include availability/lead time info
        include_eol: Include End-of-Life dates

    Returns:
        JSON string with current prices from Cisco API

    Example:
        >>> lookup_cisco_prices(["C9300-24T-E", "CON-SNT-C93002TE"])
    """
    if len(skus) > 50:
        return json.dumps({"error": "Maximum 50 SKUs for real-time lookup"})

    db = get_db_session()
    try:
        service = CiscoPricingService(db)

        request = CiscoPriceLookupRequest(
            skus=skus,
            price_list=price_list,
            include_availability=include_availability,
            include_eol=include_eol,
        )

        result = service.lookup_prices_sync(request)

        response = {
            "price_list": result.price_list,
            "total": result.total,
            "found": result.found,
            "not_found": result.not_found,
            "items": [
                {
                    "sku": item.sku,
                    "description": item.description,
                    "list_price": item.list_price,
                    "currency": item.currency,
                    "product_type": item.product_type,
                    "erp_family": item.erp_family,
                    "web_orderable": item.web_orderable,
                    "lead_time": item.lead_time,
                    "stockable": item.stockable,
                    "end_of_sale_date": item.end_of_sale_date,
                    "last_date_of_support": item.last_date_of_support,
                    "error": item.error,
                }
                for item in result.items
            ],
        }

        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.tool()
def list_cisco_price_lists() -> str:
    """List available Cisco price lists.

    Returns all available price list codes with their currencies and regions.
    Use these codes with sync_cisco_prices or lookup_cisco_prices.

    Returns:
        JSON string with available price lists
    """
    # Import from cisco_connector
    try:
        import sys
        from pathlib import Path
        connector_path = Path.home() / "cisco_connector" / "src"
        if str(connector_path) not in sys.path:
            sys.path.insert(0, str(connector_path))
        from cisco_catalog_mcp.constants import PRICE_LISTS
        return json.dumps(PRICE_LISTS, indent=2)
    except ImportError:
        # Fallback to common ones
        return json.dumps({
            "GLUS": {"description": "US pricing", "currency": "USD"},
            "GLEMEA": {"description": "EMEA pricing", "currency": "USD"},
            "GLEURO": {"description": "Euro pricing", "currency": "EUR"},
            "GLCA": {"description": "Canadian pricing", "currency": "CAD"},
            "GLGB": {"description": "UK pricing", "currency": "GBP"},
        }, indent=2)


@mcp.tool()
def list_price_import_formats() -> str:
    """List available preset formats for price import.

    Shows the column mappings used by each preset format so you can
    verify which format to use for your distributor's CSV export.

    Returns:
        JSON string with format names and their column mappings
    """
    result = {
        "formats": {
            name: {
                "sku_column": mapping.sku_column,
                "price_column": mapping.price_column,
                "name_column": mapping.name_column,
                "vendor_column": mapping.vendor_column,
            }
            for name, mapping in PRESET_MAPPINGS.items()
        },
        "auto_detection": {
            "description": "Use format='auto' to automatically detect the format based on column headers",
            "supported_distributors": ["Ingram Micro", "TD SYNNEX", "D&H"],
            "fallback": "Falls back to pattern-based column detection if no preset matches",
        },
    }
    return json.dumps(result, indent=2)


# Entry point for running the MCP server
if __name__ == "__main__":
    mcp.run()
