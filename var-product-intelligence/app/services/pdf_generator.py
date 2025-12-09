"""PDF generation service using ReportLab."""

import os
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.models.product import Product
from app.models.category import Category


# Logo placeholder dimensions: 200x60 pixels (approximately 2.8" x 0.83" at 72 DPI)
LOGO_WIDTH = 2.8 * inch
LOGO_HEIGHT = 0.83 * inch


class PDFGenerator:
    """Service for generating product comparison PDFs."""

    def __init__(self):
        """Initialize PDF generator with styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="ComparisonTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                alignment=TA_CENTER,
                spaceAfter=12,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="ComparisonSubtitle",
                parent=self.styles["Heading2"],
                fontSize=14,
                alignment=TA_CENTER,
                textColor=colors.grey,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Metadata",
                parent=self.styles["Normal"],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.grey,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading3"],
                fontSize=12,
                spaceBefore=18,
                spaceAfter=6,
                textColor=colors.HexColor("#333333"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Notes",
                parent=self.styles["Normal"],
                fontSize=10,
                leftIndent=20,
            )
        )

    def generate_comparison_pdf(
        self,
        products: list[Product],
        category: Category,
        include_pricing: bool = True,
        include_attributes: list[str] | None = None,
        title: str | None = None,
        notes: str | None = None,
        prepared_by: str | None = None,
    ) -> bytes:
        """Generate a comparison PDF for the given products.

        Args:
            products: List of products to compare
            category: Category of the products
            include_pricing: Whether to include price columns
            include_attributes: Specific attributes to include (None = all)
            title: Custom title for the document
            notes: Optional notes to include
            prepared_by: Username who prepared the document

        Returns:
            PDF as bytes
        """
        # Determine page orientation based on product count
        if len(products) > 3:
            pagesize = landscape(letter)
        else:
            pagesize = letter

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        content = []

        # Title section
        content.extend(self._build_title_section(title, category, prepared_by))

        # Overview section
        content.extend(self._build_overview_section(products))

        # Comparison table
        content.extend(
            self._build_comparison_table(
                products, category, include_pricing, include_attributes
            )
        )

        # Notes section
        if notes:
            content.extend(self._build_notes_section(notes))

        # Build PDF
        doc.build(content)
        return buffer.getvalue()

    def _build_title_section(
        self,
        title: str | None,
        category: Category,
        prepared_by: str | None,
    ) -> list:
        """Build the title section of the PDF."""
        content = []

        # Logo placeholder
        # Note: Replace this with actual logo loading when logo is available
        # Logo should be 200x60 pixels (PNG recommended)
        content.append(Spacer(1, 0.5 * inch))

        # Placeholder text for logo
        logo_placeholder = Paragraph(
            "<b>[LOGO PLACEHOLDER - 200x60 pixels]</b>",
            self.styles["Metadata"],
        )
        content.append(logo_placeholder)
        content.append(Spacer(1, 0.3 * inch))

        # Title
        display_title = title or "Product Comparison"
        content.append(Paragraph(display_title, self.styles["ComparisonTitle"]))

        # Category subtitle
        content.append(Paragraph(category.name, self.styles["ComparisonSubtitle"]))

        # Metadata
        today = datetime.now().strftime("%B %d, %Y")
        metadata_text = f"Generated: {today}"
        if prepared_by:
            metadata_text += f" | Prepared by: {prepared_by}"
        content.append(Paragraph(metadata_text, self.styles["Metadata"]))
        content.append(Spacer(1, 0.5 * inch))

        return content

    def _build_overview_section(self, products: list[Product]) -> list:
        """Build the overview section."""
        content = []

        vendor_count = len(set(p.vendor_id for p in products))
        overview_text = f"Comparing {len(products)} products across {vendor_count} vendor{'s' if vendor_count > 1 else ''}"

        content.append(Paragraph("Overview", self.styles["SectionHeader"]))
        content.append(Paragraph(overview_text, self.styles["Normal"]))
        content.append(Spacer(1, 0.3 * inch))

        return content

    def _build_comparison_table(
        self,
        products: list[Product],
        category: Category,
        include_pricing: bool,
        include_attributes: list[str] | None,
    ) -> list:
        """Build the main comparison table."""
        content = []
        content.append(Paragraph("Comparison", self.styles["SectionHeader"]))

        # Determine which attributes to include
        schema = category.attribute_schema or {}
        schema_properties = schema.get("properties", {})

        if include_attributes:
            # Use only specified attributes
            attributes_to_show = [
                (key, schema_properties.get(key, {}))
                for key in include_attributes
                if key in schema_properties
            ]
        else:
            # Use all attributes from schema
            attributes_to_show = list(schema_properties.items())

        # Build table data
        table_data = []

        # Header row
        header_row = ["Attribute"] + [
            Paragraph(f"<b>{p.name}</b>", self.styles["Normal"]) for p in products
        ]
        table_data.append(header_row)

        # Vendor row
        vendor_row = ["Vendor"] + [
            p.vendor.name if p.vendor else p.vendor_id for p in products
        ]
        table_data.append(vendor_row)

        # SKU row
        sku_row = ["SKU"] + [p.sku for p in products]
        table_data.append(sku_row)

        # Price row
        if include_pricing:
            price_row = ["List Price"] + [
                self._format_price(p.list_price_float, p.currency) for p in products
            ]
            table_data.append(price_row)

        # Attribute rows
        for attr_key, attr_def in attributes_to_show:
            label = attr_def.get("label", attr_key.replace("_", " ").title())
            row = [label]

            for product in products:
                attrs = product.attributes or {}
                value = attrs.get(attr_key)
                row.append(self._format_attribute_value(value))

            table_data.append(row)

        # Calculate column widths
        num_cols = len(products) + 1
        available_width = 7.5 * inch if len(products) <= 3 else 10 * inch
        col_width = available_width / num_cols
        col_widths = [col_width] * num_cols

        # Create table
        table = Table(table_data, colWidths=col_widths)

        # Apply styling
        style = TableStyle(
            [
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 8),
                # First column (attribute names)
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#ecf0f1")),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                # Data cells
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                # Alternating row colors
                ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ]
        )
        table.setStyle(style)

        content.append(table)
        content.append(Spacer(1, 0.3 * inch))

        return content

    def _build_notes_section(self, notes: str) -> list:
        """Build the notes section."""
        content = []
        content.append(Paragraph("Notes", self.styles["SectionHeader"]))

        # Standard disclaimer
        content.append(
            Paragraph(
                "• All prices are MSRP and subject to change",
                self.styles["Notes"],
            )
        )

        # Custom notes
        for line in notes.split("\n"):
            if line.strip():
                content.append(Paragraph(f"• {line.strip()}", self.styles["Notes"]))

        return content

    def _format_price(self, price: float | None, currency: str = "USD") -> str:
        """Format a price for display."""
        if price is None:
            return "N/A"

        if currency == "USD":
            return f"${price:,.2f}"
        else:
            return f"{price:,.2f} {currency}"

    def _format_attribute_value(self, value: Any) -> str:
        """Format an attribute value for display."""
        if value is None:
            return "—"
        elif isinstance(value, bool):
            return "Yes" if value else "No"
        elif isinstance(value, list):
            return ", ".join(str(v) for v in value)
        elif isinstance(value, (int, float)):
            return f"{value:,}"
        else:
            return str(value)
