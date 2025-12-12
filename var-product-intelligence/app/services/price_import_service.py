"""Price import service for bulk loading prices from CSV files."""

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.vendor import Vendor
from app.models.category import Category
from app.schemas.price_import import (
    PriceImportRequest,
    PriceImportResponse,
    PriceImportItem,
    PriceExportRequest,
    PriceExportResponse,
    ColumnMapping,
)


# Common column name patterns for auto-detection
SKU_PATTERNS = [
    r"^sku$", r"^part.?num", r"^part.?no", r"^item.?num", r"^item.?no",
    r"^mfg.?part", r"^mfr.?part", r"^vendor.?part", r"^product.?id",
    r"^material", r"^item$", r"^part$", r"^pn$", r"^mpn$",
]

PRICE_PATTERNS = [
    r"^price$", r"^list.?price", r"^msrp", r"^unit.?price", r"^cost",
    r"^dealer.?price", r"^reseller", r"^your.?price", r"^net.?price",
    r"^ext.?price", r"^amount", r"^\$",
]

NAME_PATTERNS = [
    r"^name$", r"^description", r"^product.?name", r"^item.?desc",
    r"^short.?desc", r"^title", r"^product$",
]

VENDOR_PATTERNS = [
    r"^vendor$", r"^manufacturer", r"^mfg$", r"^mfr$", r"^brand$",
    r"^make$", r"^supplier",
]


# Preset column mappings for common distributors
PRESET_MAPPINGS = {
    "ingram": ColumnMapping(
        sku_column="Ingram Part Number",
        price_column="Customer Price",
        name_column="Description",
        vendor_column="Vendor Name",
    ),
    "synnex": ColumnMapping(
        sku_column="MFG_PART_NUM",
        price_column="UNIT_PRICE",
        name_column="DESCRIPTION",
        vendor_column="MFG_NAME",
    ),
    "dnh": ColumnMapping(
        sku_column="Part Number",
        price_column="Price",
        name_column="Description",
        vendor_column="Manufacturer",
    ),
    "generic": ColumnMapping(
        sku_column="sku",
        price_column="price",
        name_column="name",
        vendor_column="vendor",
    ),
}


class PriceImportService:
    """Service for importing prices from CSV files."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def import_prices(self, request: PriceImportRequest) -> PriceImportResponse:
        """Import prices from a CSV file.

        Args:
            request: Import request with file path and options

        Returns:
            PriceImportResponse with results
        """
        file_path = Path(request.file_path)
        if not file_path.exists():
            return PriceImportResponse(
                success=False,
                file_path=str(file_path),
                format_detected="unknown",
                price_type=request.price_type,
                total_rows=0,
                matched=0,
                created=0,
                updated=0,
                skipped=0,
                errors=1,
                warnings=[f"File not found: {file_path}"],
                dry_run=request.dry_run,
            )

        # Read CSV and detect/get column mapping
        try:
            rows, headers = self._read_csv(file_path)
        except Exception as e:
            return PriceImportResponse(
                success=False,
                file_path=str(file_path),
                format_detected="unknown",
                price_type=request.price_type,
                total_rows=0,
                matched=0,
                created=0,
                updated=0,
                skipped=0,
                errors=1,
                warnings=[f"Failed to read CSV: {str(e)}"],
                dry_run=request.dry_run,
            )

        # Get column mapping
        mapping, format_name = self._get_column_mapping(
            request.format, request.custom_mapping, headers
        )

        if not mapping:
            return PriceImportResponse(
                success=False,
                file_path=str(file_path),
                format_detected="unknown",
                price_type=request.price_type,
                total_rows=len(rows),
                matched=0,
                created=0,
                updated=0,
                skipped=0,
                errors=1,
                warnings=[
                    f"Could not detect column mapping. Headers found: {headers}",
                    "Use format='custom' with custom_mapping to specify columns.",
                ],
                dry_run=request.dry_run,
            )

        # Process rows
        items = []
        matched = 0
        created = 0
        updated = 0
        skipped = 0
        errors = 0
        warnings = []

        for row in rows:
            item = self._process_row(
                row=row,
                mapping=mapping,
                request=request,
            )
            items.append(item)

            if item.action == "created":
                created += 1
                matched += 1
            elif item.action == "updated":
                updated += 1
                matched += 1
            elif item.action == "skipped":
                skipped += 1
            elif item.action == "error":
                errors += 1

        # Commit if not dry run
        if not request.dry_run and (created > 0 or updated > 0):
            self.db.commit()

        return PriceImportResponse(
            success=errors == 0,
            file_path=str(file_path),
            format_detected=format_name,
            price_type=request.price_type,
            total_rows=len(rows),
            matched=matched,
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            items=items,
            warnings=warnings,
            dry_run=request.dry_run,
        )

    def export_prices(self, request: PriceExportRequest) -> PriceExportResponse:
        """Export prices to a CSV file.

        Args:
            request: Export request with file path and filters

        Returns:
            PriceExportResponse with results
        """
        query = self.db.query(Product)

        if request.vendor_id:
            query = query.filter(Product.vendor_id == request.vendor_id)
        if request.category_id:
            query = query.filter(Product.category_id == request.category_id)

        products = query.all()

        with_prices = 0
        without_prices = 0

        file_path = Path(request.file_path)
        with open(file_path, "w", newline="") as f:
            if request.format == "detailed":
                fieldnames = [
                    "sku", "name", "vendor_id", "category_id",
                    "list_price", "cost_price", "product_family",
                    "lifecycle_status", "datasheet_url"
                ]
            else:
                fieldnames = ["sku", "name", "vendor_id", "list_price"]
                if request.include_cost:
                    fieldnames.append("cost_price")

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for product in products:
                row = {
                    "sku": product.sku,
                    "name": product.name,
                    "vendor_id": product.vendor_id,
                    "list_price": product.list_price_float or "",
                }

                if request.format == "detailed":
                    row.update({
                        "category_id": product.category_id,
                        "cost_price": product.cost_price_float or "",
                        "product_family": product.product_family or "",
                        "lifecycle_status": product.lifecycle_status or "",
                        "datasheet_url": product.datasheet_url or "",
                    })
                elif request.include_cost:
                    row["cost_price"] = product.cost_price_float or ""

                writer.writerow(row)

                if product.list_price is not None:
                    with_prices += 1
                else:
                    without_prices += 1

        return PriceExportResponse(
            success=True,
            file_path=str(file_path),
            total_products=len(products),
            with_prices=with_prices,
            without_prices=without_prices,
        )

    def _read_csv(self, file_path: Path) -> tuple[list[dict], list[str]]:
        """Read CSV file and return rows and headers."""
        rows = []
        headers = []

        with open(file_path, "r", encoding="utf-8-sig") as f:
            # Try to detect delimiter
            sample = f.read(4096)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel  # Default to comma

            reader = csv.DictReader(f, dialect=dialect)
            headers = reader.fieldnames or []

            for row in reader:
                rows.append(row)

        return rows, headers

    def _get_column_mapping(
        self,
        format_name: str,
        custom_mapping: ColumnMapping | None,
        headers: list[str],
    ) -> tuple[ColumnMapping | None, str]:
        """Get column mapping based on format or auto-detect."""
        if format_name == "custom" and custom_mapping:
            return custom_mapping, "custom"

        if format_name in PRESET_MAPPINGS:
            return PRESET_MAPPINGS[format_name], format_name

        if format_name == "auto":
            # Try preset formats first
            for preset_name, preset_mapping in PRESET_MAPPINGS.items():
                if (preset_mapping.sku_column in headers and
                        preset_mapping.price_column in headers):
                    return preset_mapping, preset_name

            # Auto-detect columns
            detected = self._auto_detect_columns(headers)
            if detected:
                return detected, "auto-detected"

        return None, "unknown"

    def _auto_detect_columns(self, headers: list[str]) -> ColumnMapping | None:
        """Auto-detect column mapping from headers."""
        headers_lower = {h.lower().strip(): h for h in headers}

        sku_col = None
        price_col = None
        name_col = None
        vendor_col = None

        # Find SKU column
        for pattern in SKU_PATTERNS:
            for header_lower, header_orig in headers_lower.items():
                if re.search(pattern, header_lower, re.IGNORECASE):
                    sku_col = header_orig
                    break
            if sku_col:
                break

        # Find Price column
        for pattern in PRICE_PATTERNS:
            for header_lower, header_orig in headers_lower.items():
                if re.search(pattern, header_lower, re.IGNORECASE):
                    price_col = header_orig
                    break
            if price_col:
                break

        # Find Name column (optional)
        for pattern in NAME_PATTERNS:
            for header_lower, header_orig in headers_lower.items():
                if re.search(pattern, header_lower, re.IGNORECASE):
                    name_col = header_orig
                    break
            if name_col:
                break

        # Find Vendor column (optional)
        for pattern in VENDOR_PATTERNS:
            for header_lower, header_orig in headers_lower.items():
                if re.search(pattern, header_lower, re.IGNORECASE):
                    vendor_col = header_orig
                    break
            if vendor_col:
                break

        if sku_col and price_col:
            return ColumnMapping(
                sku_column=sku_col,
                price_column=price_col,
                name_column=name_col,
                vendor_column=vendor_col,
            )

        return None

    def _process_row(
        self,
        row: dict,
        mapping: ColumnMapping,
        request: PriceImportRequest,
    ) -> PriceImportItem:
        """Process a single row from the CSV."""
        # Get SKU
        sku = row.get(mapping.sku_column, "").strip()
        if not sku:
            return PriceImportItem(
                sku="",
                action="error",
                new_price=0,
                message="Missing SKU",
            )

        # Get price
        price_str = row.get(mapping.price_column, "").strip()
        try:
            price = self._parse_price(price_str)
            if price is None:
                return PriceImportItem(
                    sku=sku,
                    action="skipped",
                    new_price=0,
                    message=f"Invalid price: {price_str}",
                )
        except Exception as e:
            return PriceImportItem(
                sku=sku,
                action="error",
                new_price=0,
                message=f"Price parse error: {str(e)}",
            )

        # Get optional fields
        name = None
        if mapping.name_column:
            name = row.get(mapping.name_column, "").strip() or None

        vendor_id = request.vendor_id
        if not vendor_id and mapping.vendor_column:
            vendor_name = row.get(mapping.vendor_column, "").strip()
            if vendor_name:
                vendor_id = self._resolve_vendor_id(vendor_name)

        # Look up product
        product = self.db.query(Product).filter(Product.sku == sku).first()

        if product:
            # Update existing product
            if not request.update_existing:
                return PriceImportItem(
                    sku=sku,
                    name=product.name,
                    old_price=product.list_price_float if request.price_type == "list" else product.cost_price_float,
                    new_price=price,
                    action="skipped",
                    message="Update disabled",
                )

            old_price = (
                product.list_price_float
                if request.price_type == "list"
                else product.cost_price_float
            )

            if not request.dry_run:
                if request.price_type == "list":
                    product.list_price = Decimal(str(price))
                else:
                    product.cost_price = Decimal(str(price))

            return PriceImportItem(
                sku=sku,
                name=product.name,
                old_price=old_price,
                new_price=price,
                action="updated",
                message=None,
            )
        else:
            # Create new product
            if not request.create_missing:
                return PriceImportItem(
                    sku=sku,
                    name=name,
                    new_price=price,
                    action="skipped",
                    message="Product not found (create_missing=False)",
                )

            if not vendor_id:
                return PriceImportItem(
                    sku=sku,
                    name=name,
                    new_price=price,
                    action="error",
                    message="Cannot create product: no vendor specified",
                )

            category_id = request.category_id or "uncategorized"

            if not request.dry_run:
                # Ensure category exists
                category = self.db.query(Category).filter(
                    Category.id == category_id
                ).first()
                if not category:
                    category = Category(
                        id=category_id,
                        name=category_id.replace("-", " ").title(),
                    )
                    self.db.add(category)
                    self.db.flush()

                new_product = Product(
                    sku=sku,
                    name=name or sku,
                    vendor_id=vendor_id,
                    category_id=category_id,
                )
                if request.price_type == "list":
                    new_product.list_price = Decimal(str(price))
                else:
                    new_product.cost_price = Decimal(str(price))

                self.db.add(new_product)

            return PriceImportItem(
                sku=sku,
                name=name or sku,
                new_price=price,
                action="created",
                message=None,
            )

    def _parse_price(self, price_str: str) -> float | None:
        """Parse price string to float."""
        if not price_str:
            return None

        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[$€£¥,\s]", "", price_str)

        # Handle parentheses for negative (accounting format)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _resolve_vendor_id(self, vendor_name: str) -> str | None:
        """Try to find vendor ID from name."""
        # Normalize vendor name
        vendor_name_lower = vendor_name.lower().strip()

        # Common mappings
        vendor_aliases = {
            "cisco": ["cisco", "cisco systems"],
            "meraki": ["meraki", "cisco meraki"],
            "hpe-aruba": ["aruba", "hpe aruba", "aruba networks", "hewlett packard enterprise"],
            "hpe": ["hpe", "hp", "hewlett packard", "hewlett-packard"],
            "juniper-mist": ["mist", "juniper mist"],
            "juniper": ["juniper", "juniper networks"],
            "fortinet": ["fortinet", "fortigate"],
            "palo-alto": ["palo alto", "palo alto networks", "pan"],
            "dell": ["dell", "dell emc", "dell technologies"],
        }

        for vendor_id, aliases in vendor_aliases.items():
            if vendor_name_lower in aliases:
                # Verify vendor exists
                vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
                if vendor:
                    return vendor_id

        # Try exact match
        vendor = self.db.query(Vendor).filter(
            Vendor.name.ilike(f"%{vendor_name}%")
        ).first()
        if vendor:
            return vendor.id

        return None
