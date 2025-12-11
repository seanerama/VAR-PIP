"""Seed data export and import utilities.

Usage:
    # Export current database to seed file
    uv run python -m app.scripts.seed export

    # Load seed data into database
    uv run python -m app.scripts.seed load

    # Load seed data (clear existing first)
    uv run python -m app.scripts.seed load --clear
"""

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.database import get_db, engine, Base
from app.models.product import Product
from app.models.vendor import Vendor
from app.models.category import Category


SEED_FILE = Path(__file__).parent.parent.parent / "seed_data.json"


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def export_seed_data(output_path: Path = SEED_FILE) -> dict:
    """Export all vendors, categories, and products to JSON."""
    db = next(get_db())

    try:
        # Export vendors
        vendors = []
        for v in db.query(Vendor).all():
            vendors.append({
                "id": v.id,
                "name": v.name,
                "website": v.website,
                "partner_portal_url": v.partner_portal_url,
            })

        # Export categories
        categories = []
        for c in db.query(Category).all():
            categories.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "attribute_schema": c.attribute_schema,
            })

        # Export products
        products = []
        for p in db.query(Product).all():
            products.append({
                "id": p.id,
                "sku": p.sku,
                "vendor_id": p.vendor_id,
                "category_id": p.category_id,
                "name": p.name,
                "product_family": p.product_family,
                "list_price": float(p.list_price) if p.list_price else None,
                "cost_price": float(p.cost_price) if p.cost_price else None,
                "currency": p.currency,
                "lifecycle_status": p.lifecycle_status,
                "warranty_years": p.warranty_years,
                "attributes": p.attributes,
                "datasheet_url": p.datasheet_url,
                "image_url": p.image_url,
                "notes": p.notes,
            })

        seed_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "vendors": vendors,
            "categories": categories,
            "products": products,
        }

        # Write to file
        with open(output_path, "w") as f:
            json.dump(seed_data, f, indent=2, cls=DecimalEncoder)

        print(f"Exported seed data to {output_path}")
        print(f"  Vendors: {len(vendors)}")
        print(f"  Categories: {len(categories)}")
        print(f"  Products: {len(products)}")

        return seed_data

    finally:
        db.close()


def load_seed_data(input_path: Path = SEED_FILE, clear_existing: bool = False) -> dict:
    """Load seed data from JSON into database.

    Args:
        input_path: Path to seed JSON file
        clear_existing: If True, delete all existing data first

    Returns:
        Dict with counts of loaded items
    """
    if not input_path.exists():
        print(f"Error: Seed file not found: {input_path}")
        sys.exit(1)

    with open(input_path) as f:
        seed_data = json.load(f)

    db = next(get_db())

    try:
        if clear_existing:
            print("Clearing existing data...")
            db.query(Product).delete()
            db.query(Category).delete()
            db.query(Vendor).delete()
            db.commit()

        # Track what we loaded
        stats = {"vendors": 0, "categories": 0, "products": 0, "skipped": 0}

        # Load vendors
        existing_vendor_ids = {v.id for v in db.query(Vendor).all()}
        for v_data in seed_data.get("vendors", []):
            if v_data["id"] not in existing_vendor_ids:
                vendor = Vendor(
                    id=v_data["id"],
                    name=v_data["name"],
                    website=v_data.get("website"),
                    partner_portal_url=v_data.get("partner_portal_url"),
                )
                db.add(vendor)
                stats["vendors"] += 1
        db.commit()

        # Load categories
        existing_category_ids = {c.id for c in db.query(Category).all()}
        for c_data in seed_data.get("categories", []):
            if c_data["id"] not in existing_category_ids:
                category = Category(
                    id=c_data["id"],
                    name=c_data["name"],
                    description=c_data.get("description"),
                    attribute_schema=c_data.get("attribute_schema"),
                )
                db.add(category)
                stats["categories"] += 1
        db.commit()

        # Load products
        existing_skus = {(p.sku, p.vendor_id) for p in db.query(Product).all()}
        for p_data in seed_data.get("products", []):
            key = (p_data["sku"], p_data["vendor_id"])
            if key not in existing_skus:
                product = Product(
                    id=p_data["id"],
                    sku=p_data["sku"],
                    vendor_id=p_data["vendor_id"],
                    category_id=p_data["category_id"],
                    name=p_data["name"],
                    product_family=p_data.get("product_family"),
                    list_price=p_data.get("list_price"),
                    cost_price=p_data.get("cost_price"),
                    currency=p_data.get("currency", "USD"),
                    lifecycle_status=p_data.get("lifecycle_status", "active"),
                    warranty_years=p_data.get("warranty_years"),
                    attributes=p_data.get("attributes"),
                    datasheet_url=p_data.get("datasheet_url"),
                    image_url=p_data.get("image_url"),
                    notes=p_data.get("notes"),
                )
                db.add(product)
                stats["products"] += 1
            else:
                stats["skipped"] += 1
        db.commit()

        print(f"Loaded seed data from {input_path}")
        print(f"  Vendors: {stats['vendors']} new")
        print(f"  Categories: {stats['categories']} new")
        print(f"  Products: {stats['products']} new, {stats['skipped']} skipped (already exist)")

        return stats

    finally:
        db.close()


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "export":
        export_seed_data()
    elif command == "load":
        clear = "--clear" in sys.argv
        load_seed_data(clear_existing=clear)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
