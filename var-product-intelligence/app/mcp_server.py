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
from app.schemas.extract import UrlExtractionRequest, BatchUrlExtractionRequest
from app.schemas.compare import CompareRequest

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

    Returns:
        JSON string with extraction results, including:
        - source_type: 'pdf', 'html', or 'pdf_listing'
        - extracted_product: The extracted product data (if successful)
        - product_saved: Whether the product was saved to database
        - saved_product_id: ID of saved product (if saved)
        - pdf_links_found: List of PDF links (if source_type is 'pdf_listing')
    """
    db = get_db_session()
    try:
        service = ExtractionService(db)

        request = UrlExtractionRequest(
            url=url,
            category_id=category_id,
            vendor_id=vendor_id,
            save_product=save_product,
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

        if result.extracted_product:
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


# Entry point for running the MCP server
if __name__ == "__main__":
    mcp.run()
