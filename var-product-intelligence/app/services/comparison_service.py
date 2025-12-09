"""Comparison service for generating product comparisons."""

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.product import Product
from app.models.category import Category
from app.services.pdf_generator import PDFGenerator
from app.schemas.compare import CompareRequest, CompareResponse


class ComparisonService:
    """Service for product comparison operations."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.pdf_generator = PDFGenerator()
        self.output_dir = Path(settings.pdf_output_dir)
        self.expiry_hours = settings.pdf_expiry_hours

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_comparison(
        self,
        request: CompareRequest,
        prepared_by: str | None = None,
    ) -> CompareResponse:
        """Create a product comparison PDF.

        Args:
            request: Comparison request with product IDs and options
            prepared_by: Username who requested the comparison

        Returns:
            CompareResponse with PDF URL and metadata

        Raises:
            ValueError: If validation fails
        """
        # Fetch products
        products = (
            self.db.query(Product)
            .filter(Product.id.in_(request.product_ids))
            .all()
        )

        # Validate all products exist
        found_ids = {p.id for p in products}
        missing_ids = set(request.product_ids) - found_ids
        if missing_ids:
            raise ValueError(f"Products not found: {', '.join(missing_ids)}")

        # Validate all products are same category
        categories = set(p.category_id for p in products)
        if len(categories) > 1:
            raise ValueError(
                f"All products must be from the same category. Found: {', '.join(categories)}"
            )

        # Get category
        category_id = products[0].category_id
        category = self.db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise ValueError(f"Category '{category_id}' not found")

        # Order products to match requested order
        product_order = {pid: idx for idx, pid in enumerate(request.product_ids)}
        products = sorted(products, key=lambda p: product_order[p.id])

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_comparison_pdf(
            products=products,
            category=category,
            include_pricing=request.include_pricing,
            include_attributes=request.include_attributes,
            title=request.title,
            notes=request.notes,
            prepared_by=prepared_by,
        )

        # Generate comparison ID and save PDF
        comparison_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{comparison_id}_{timestamp}.pdf"
        filepath = self.output_dir / filename

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(hours=self.expiry_hours)

        return CompareResponse(
            comparison_id=comparison_id,
            pdf_url=f"/compare/{comparison_id}/download",
            expires_at=expires_at,
            products_compared=len(products),
        )

    def get_pdf_path(self, comparison_id: str) -> tuple[Path | None, bool]:
        """Get the path to a comparison PDF.

        Checks if the PDF exists and if it's expired.

        Args:
            comparison_id: The comparison ID

        Returns:
            Tuple of (path or None, is_expired)
        """
        # Find matching file
        pattern = f"{comparison_id}_*.pdf"
        matching_files = list(self.output_dir.glob(pattern))

        if not matching_files:
            return None, False

        filepath = matching_files[0]

        # Check expiry by parsing timestamp from filename
        try:
            filename = filepath.stem  # Remove .pdf
            parts = filename.split("_")
            if len(parts) >= 2:
                timestamp_str = parts[1]
                file_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                age = datetime.utcnow() - file_time

                if age > timedelta(hours=self.expiry_hours):
                    # File is expired - delete it
                    filepath.unlink(missing_ok=True)
                    return None, True
        except (ValueError, IndexError):
            # Can't parse timestamp, just check if file exists
            pass

        return filepath, False

    def cleanup_expired(self) -> int:
        """Clean up all expired PDFs.

        Returns:
            Number of files deleted
        """
        deleted = 0
        now = datetime.utcnow()

        for filepath in self.output_dir.glob("*.pdf"):
            try:
                filename = filepath.stem
                parts = filename.split("_")
                if len(parts) >= 2:
                    timestamp_str = parts[1]
                    file_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    age = now - file_time

                    if age > timedelta(hours=self.expiry_hours):
                        filepath.unlink(missing_ok=True)
                        deleted += 1
            except (ValueError, IndexError):
                continue

        return deleted
