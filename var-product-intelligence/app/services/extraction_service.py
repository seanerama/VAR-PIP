"""AI-powered datasheet extraction service using Anthropic Claude."""

import base64
import json
import re
import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import anthropic
import fitz  # pymupdf for PDF text extraction
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.models.vendor import Vendor
from app.models.category import Category
from app.models.product import Product
from app.schemas.extract import (
    ExtractionRequest,
    ExtractionResponse,
    ExtractedProduct,
    ExtractedField,
    UrlExtractionRequest,
    UrlExtractionResponse,
    PdfLink,
    BatchUrlExtractionRequest,
    BatchUrlExtractionResponse,
    BatchExtractionResult,
    MultiProductResult,
)


class ExtractionService:
    """Service for extracting product data from datasheets using Claude."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _save_extracted_product(
        self,
        extracted_product: ExtractedProduct,
        vendor_id: str,
        category_id: str,
        datasheet_url: str | None = None,
    ) -> str:
        """Save extracted product to database.

        Args:
            extracted_product: The extracted product data
            vendor_id: Vendor ID
            category_id: Category ID
            datasheet_url: Optional URL of the source datasheet

        Returns:
            The saved product's ID

        Raises:
            ValueError: If SKU is missing or product already exists
        """
        if not extracted_product.sku:
            raise ValueError("Cannot save product: SKU is missing from extraction")

        # Check for duplicate SKU
        existing = (
            self.db.query(Product)
            .filter(Product.sku == extracted_product.sku)
            .first()
        )
        if existing:
            raise ValueError(
                f"Product with SKU '{extracted_product.sku}' already exists (ID: {existing.id})"
            )

        # Convert extracted attributes to simple values (strip confidence metadata)
        attributes = {}
        for key, field in extracted_product.attributes.items():
            if field.value is not None:
                attributes[key] = field.value

        # Create product
        product = Product(
            id=str(uuid.uuid4()),
            sku=extracted_product.sku,
            name=extracted_product.name or extracted_product.sku,
            vendor_id=vendor_id,
            category_id=category_id,
            product_family=extracted_product.product_family,
            attributes=attributes,
            datasheet_url=datasheet_url,
        )

        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)

        return product.id

    def extract_from_datasheet(
        self, request: ExtractionRequest
    ) -> ExtractionResponse:
        """Extract product data from a PDF datasheet.

        Args:
            request: Extraction request with PDF content and metadata

        Returns:
            ExtractionResponse with extracted product data

        Raises:
            ValueError: If category not found or extraction fails
        """
        extraction_id = str(uuid.uuid4())
        vendor_created = False

        # Get category and schema
        category = (
            self.db.query(Category)
            .filter(Category.id == request.category_id)
            .first()
        )
        if not category:
            raise ValueError(f"Category '{request.category_id}' not found")

        # Auto-create vendor if not exists
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == request.vendor_id)
            .first()
        )
        if not vendor:
            vendor = Vendor(
                id=request.vendor_id,
                name=request.vendor_id.replace("_", " ").title(),
            )
            self.db.add(vendor)
            self.db.commit()
            vendor_created = True

        # Build extraction prompt
        prompt = self._build_extraction_prompt(category)

        # Decode PDF
        try:
            pdf_bytes = base64.b64decode(request.file_content)
        except Exception as e:
            raise ValueError(f"Invalid base64-encoded PDF content: {e}")

        # Call Claude API
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": request.file_content,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )
        except anthropic.APIError as e:
            raise ValueError(f"Claude API error: {e}")

        # Parse response
        response_text = message.content[0].text
        extracted_data = self._parse_extraction_response(response_text)

        # Build extracted product
        extracted_product = self._build_extracted_product(extracted_data)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            extracted_product, category.attribute_schema
        )

        # Determine status
        if confidence_score >= 0.8:
            status = "completed"
        elif confidence_score >= 0.5:
            status = "partial"
        else:
            status = "failed"

        # Handle auto-save if requested
        product_saved = False
        saved_product_id = None
        warnings = extracted_data.get("warnings", [])

        if request.save_product and status in ("completed", "partial"):
            try:
                saved_product_id = self._save_extracted_product(
                    extracted_product=extracted_product,
                    vendor_id=request.vendor_id,
                    category_id=request.category_id,
                )
                product_saved = True
            except ValueError as e:
                warnings.append(f"Auto-save failed: {str(e)}")

        return ExtractionResponse(
            extraction_id=extraction_id,
            status=status,
            confidence_score=confidence_score,
            extracted_product=extracted_product,
            warnings=warnings,
            vendor_created=vendor_created,
            product_saved=product_saved,
            saved_product_id=saved_product_id,
        )

    def _build_extraction_prompt(self, category: Category) -> str:
        """Build the extraction prompt for Claude.

        Args:
            category: Category with attribute schema

        Returns:
            Extraction prompt string
        """
        schema = category.attribute_schema or {}
        schema_json = json.dumps(schema, indent=2)

        return f"""You are a product data extraction specialist. Extract structured
product information from the provided datasheet PDF.

Target Category: {category.name}

Expected Attributes Schema:
{schema_json}

Instructions:
1. Extract all fields matching the schema
2. For each field, provide:
   - value: the extracted value (use exact types from schema)
   - confidence: "high", "medium", or "low"
   - source_note: brief note about where in document this was found
3. Mark missing fields as null with explanation in source_note
4. Normalize values to schema format/units:
   - Enums: use exact values from schema
   - Booleans: true/false
   - Numbers: numeric values only
   - Arrays: JSON arrays
5. Extract SKU, product name, and product family

Output as valid JSON with this exact structure:
{{
  "sku": "extracted SKU or null",
  "name": "product name or null",
  "product_family": "product line/series or null",
  "attributes": {{
    "attribute_key": {{
      "value": extracted_value_or_null,
      "confidence": "high|medium|low",
      "source_note": "where this was found or why it's missing"
    }}
  }},
  "warnings": ["list of any issues or notes"]
}}

Important: Return ONLY the JSON object, no additional text or markdown formatting."""

    def _build_multi_product_extraction_prompt(self, category: Category) -> str:
        """Build extraction prompt for multiple products from family datasheets.

        Args:
            category: Category with attribute schema

        Returns:
            Multi-product extraction prompt string
        """
        schema = category.attribute_schema or {}

        # Extract just the property names for a compact schema reference
        properties = schema.get("properties", {})
        attr_list = ", ".join(properties.keys()) if properties else "wifi_generation, radio_config, max_throughput_mbps, bands, form_factor, uplink_speed, poe_requirement"

        return f"""You are a product data extraction specialist. This document is a FAMILY DATASHEET
containing MULTIPLE distinct products/models. Extract EACH product separately.

Target Category: {category.name}
Key attributes to extract: {attr_list}

Instructions:
1. Identify ALL distinct product models/SKUs in the document
2. For EACH product, extract its specific attributes (they may differ between models)
3. Do NOT merge products - create separate entries for each model
4. Use COMPACT output: only include "value" for attributes (no confidence/source_note needed)
5. Normalize values: booleans as true/false, numbers as numbers, arrays as JSON arrays

Output as valid JSON with this COMPACT structure:
{{
  "products": [
    {{
      "sku": "MODEL-NUMBER",
      "name": "Product Name",
      "product_family": "Series Name",
      "attributes": {{
        "wifi_generation": "wifi6",
        "radio_config": "4x4:4",
        "max_throughput_mbps": 5400,
        "form_factor": "indoor",
        "uplink_speed": "2.5g"
      }}
    }}
  ],
  "warnings": []
}}

CRITICAL:
- Extract EVERY distinct product model as a separate entry
- Use exact model number/SKU as it appears
- Keep attribute values simple (just the value, no metadata)

Important: Return ONLY the JSON object, no markdown."""

    def _parse_extraction_response(self, response_text: str) -> dict[str, Any]:
        """Parse the extraction response from Claude.

        Args:
            response_text: Raw response text from Claude

        Returns:
            Parsed extraction data
        """
        # Try to extract JSON from response
        text = response_text.strip()

        # Handle potential markdown code blocks
        if text.startswith("```"):
            # Remove markdown code block
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "sku": None,
                "name": None,
                "product_family": None,
                "attributes": {},
                "warnings": [f"Failed to parse extraction response: {e}"],
            }

    def _build_extracted_product(
        self, extracted_data: dict[str, Any]
    ) -> ExtractedProduct:
        """Build ExtractedProduct from parsed data.

        Args:
            extracted_data: Parsed extraction data

        Returns:
            ExtractedProduct instance
        """
        attributes = {}
        raw_attributes = extracted_data.get("attributes", {})

        for key, field_data in raw_attributes.items():
            if isinstance(field_data, dict):
                attributes[key] = ExtractedField(
                    value=field_data.get("value"),
                    confidence=field_data.get("confidence") or "medium",
                    source_note=field_data.get("source_note"),
                )
            else:
                # Handle case where Claude returns just the value
                attributes[key] = ExtractedField(
                    value=field_data,
                    confidence="medium",
                    source_note=None,
                )

        return ExtractedProduct(
            sku=extracted_data.get("sku"),
            name=extracted_data.get("name"),
            product_family=extracted_data.get("product_family"),
            attributes=attributes,
        )

    def _calculate_confidence(
        self,
        extracted_product: ExtractedProduct,
        schema: dict[str, Any] | None,
    ) -> float:
        """Calculate overall confidence score.

        Score is based on:
        - Percentage of schema fields extracted
        - Individual field confidence levels

        Args:
            extracted_product: Extracted product data
            schema: Category attribute schema

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if not schema or "properties" not in schema:
            # No schema to validate against
            # Base score on core fields
            core_fields = ["sku", "name"]
            found = sum(
                1
                for f in core_fields
                if getattr(extracted_product, f, None) is not None
            )
            return found / len(core_fields)

        properties = schema["properties"]
        total_fields = len(properties)

        if total_fields == 0:
            return 1.0

        # Count extracted fields and their confidence
        extracted_count = 0
        confidence_sum = 0.0
        confidence_weights = {"high": 1.0, "medium": 0.7, "low": 0.3}

        for key in properties:
            if key in extracted_product.attributes:
                field = extracted_product.attributes[key]
                if field.value is not None:
                    extracted_count += 1
                    weight = confidence_weights.get(field.confidence, 0.5)
                    confidence_sum += weight

        # Calculate score
        # 50% based on coverage, 50% based on confidence quality
        coverage_score = extracted_count / total_fields
        quality_score = (
            confidence_sum / extracted_count if extracted_count > 0 else 0
        )

        return 0.5 * coverage_score + 0.5 * quality_score

    def extract_from_url(
        self, request: UrlExtractionRequest
    ) -> UrlExtractionResponse:
        """Extract product data from a URL.

        Handles three scenarios:
        1. Direct PDF URL - downloads and extracts from PDF
        2. HTML page with PDF links - returns list of PDFs found
        3. HTML page with inline specs - extracts from page content

        Args:
            request: URL extraction request

        Returns:
            UrlExtractionResponse with extraction results or PDF list

        Raises:
            ValueError: If category not found or fetch fails
        """
        extraction_id = str(uuid.uuid4())
        vendor_created = False

        # Validate category exists
        category = (
            self.db.query(Category)
            .filter(Category.id == request.category_id)
            .first()
        )
        if not category:
            raise ValueError(f"Category '{request.category_id}' not found")

        # Auto-create vendor if not exists
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == request.vendor_id)
            .first()
        )
        if not vendor:
            vendor = Vendor(
                id=request.vendor_id,
                name=request.vendor_id.replace("_", " ").title(),
            )
            self.db.add(vendor)
            self.db.commit()
            vendor_created = True

        # Fetch URL content
        try:
            response = httpx.get(
                request.url,
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; VARProductIntelligence/1.0)"
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch URL: {e}")

        content_type = response.headers.get("content-type", "").lower()

        # Scenario 1: Direct PDF
        if "application/pdf" in content_type or request.url.lower().endswith(".pdf"):
            return self._extract_from_pdf_url(
                extraction_id=extraction_id,
                url=request.url,
                pdf_content=response.content,
                category=category,
                vendor_id=request.vendor_id,
                vendor_created=vendor_created,
                save_product=request.save_product,
                extract_all_products=request.extract_all_products,
            )

        # Scenario 2 & 3: HTML content
        if "text/html" in content_type:
            html_content = response.text
            pdf_links = self._find_pdf_links(html_content, request.url)

            # If PDF links found, return them for user selection
            if pdf_links:
                return UrlExtractionResponse(
                    extraction_id=extraction_id,
                    source_type="pdf_listing",
                    source_url=request.url,
                    pdf_links_found=pdf_links,
                    vendor_created=vendor_created,
                )

            # No PDFs found - extract from HTML content
            return self._extract_from_html(
                extraction_id=extraction_id,
                url=request.url,
                html_content=html_content,
                category=category,
                vendor_id=request.vendor_id,
                vendor_created=vendor_created,
                save_product=request.save_product,
            )

        raise ValueError(f"Unsupported content type: {content_type}")

    def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text content from PDF using pymupdf.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            Extracted text from all pages
        """
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)

    def _extract_from_pdf_url(
        self,
        extraction_id: str,
        url: str,
        pdf_content: bytes,
        category: Category,
        vendor_id: str,
        vendor_created: bool,
        save_product: bool = False,
        extract_all_products: bool = False,
    ) -> UrlExtractionResponse:
        """Extract from PDF content fetched from URL."""
        pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

        # Choose prompt based on extraction mode
        if extract_all_products:
            prompt = self._build_multi_product_extraction_prompt(category)
            max_tokens = 16384  # More tokens for multi-product responses
        else:
            prompt = self._build_extraction_prompt(category)
            max_tokens = 4096

        use_text_fallback = False
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )
        except anthropic.APIError as e:
            # Check if error is due to prompt being too long (large PDF)
            error_str = str(e)
            if "too long" in error_str.lower() or "maximum" in error_str.lower():
                use_text_fallback = True
            else:
                raise ValueError(f"Claude API error: {e}")

        # Fallback: extract text from PDF and retry with text-only
        if use_text_fallback:
            pdf_text = self._extract_text_from_pdf(pdf_content)
            text_prompt = f"""The following is text extracted from a PDF datasheet.
Please extract product information from this text.

--- PDF TEXT START ---
{pdf_text}
--- PDF TEXT END ---

{prompt}"""
            try:
                message = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": text_prompt,
                        }
                    ],
                )
            except anthropic.APIError as e:
                raise ValueError(f"Claude API error (text fallback): {e}")

        response_text = message.content[0].text
        extracted_data = self._parse_extraction_response(response_text)

        # Handle multi-product extraction mode
        if extract_all_products:
            return self._handle_multi_product_response(
                extraction_id=extraction_id,
                url=url,
                extracted_data=extracted_data,
                category=category,
                vendor_id=vendor_id,
                vendor_created=vendor_created,
                save_product=save_product,
            )

        # Single product extraction (original behavior)
        extracted_product = self._build_extracted_product(extracted_data)
        confidence_score = self._calculate_confidence(
            extracted_product, category.attribute_schema
        )

        if confidence_score >= 0.8:
            status = "completed"
        elif confidence_score >= 0.5:
            status = "partial"
        else:
            status = "failed"

        # Handle auto-save if requested
        product_saved = False
        saved_product_id = None
        warnings = extracted_data.get("warnings", [])

        if save_product and status in ("completed", "partial"):
            try:
                saved_product_id = self._save_extracted_product(
                    extracted_product=extracted_product,
                    vendor_id=vendor_id,
                    category_id=category.id,
                    datasheet_url=url,
                )
                product_saved = True
            except ValueError as e:
                warnings.append(f"Auto-save failed: {str(e)}")

        return UrlExtractionResponse(
            extraction_id=extraction_id,
            source_type="pdf",
            source_url=url,
            status=status,
            confidence_score=confidence_score,
            extracted_product=extracted_product,
            warnings=warnings,
            vendor_created=vendor_created,
            product_saved=product_saved,
            saved_product_id=saved_product_id,
        )

    def _handle_multi_product_response(
        self,
        extraction_id: str,
        url: str,
        extracted_data: dict[str, Any],
        category: Category,
        vendor_id: str,
        vendor_created: bool,
        save_product: bool,
    ) -> UrlExtractionResponse:
        """Handle multi-product extraction response."""
        warnings = extracted_data.get("warnings", [])
        products_data = extracted_data.get("products", [])
        product_results = []
        products_saved = 0

        for product_data in products_data:
            # Build extracted product for each item
            extracted_product = self._build_extracted_product(product_data)
            result = MultiProductResult(
                sku=extracted_product.sku,
                name=extracted_product.name,
                extracted_product=extracted_product,
            )

            # Try to save if requested
            if save_product and extracted_product.sku:
                try:
                    saved_id = self._save_extracted_product(
                        extracted_product=extracted_product,
                        vendor_id=vendor_id,
                        category_id=category.id,
                        datasheet_url=url,
                    )
                    result.product_saved = True
                    result.saved_product_id = saved_id
                    products_saved += 1
                except ValueError as e:
                    result.error = str(e)

            product_results.append(result)

        return UrlExtractionResponse(
            extraction_id=extraction_id,
            source_type="pdf",
            source_url=url,
            status="completed" if products_data else "failed",
            confidence_score=0.8 if products_data else 0.0,
            warnings=warnings,
            vendor_created=vendor_created,
            multi_product_mode=True,
            products_found=len(products_data),
            products_saved=products_saved,
            product_results=product_results,
        )

    def _extract_from_html(
        self,
        extraction_id: str,
        url: str,
        html_content: str,
        category: Category,
        vendor_id: str,
        vendor_created: bool,
        save_product: bool = False,
    ) -> UrlExtractionResponse:
        """Extract product data from HTML page content."""
        # Parse HTML and extract text content
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get text content
        text_content = soup.get_text(separator="\n", strip=True)

        # Limit text length for API
        if len(text_content) > 50000:
            text_content = text_content[:50000] + "\n[Content truncated...]"

        prompt = self._build_html_extraction_prompt(category, text_content)

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
        except anthropic.APIError as e:
            raise ValueError(f"Claude API error: {e}")

        response_text = message.content[0].text
        extracted_data = self._parse_extraction_response(response_text)
        extracted_product = self._build_extracted_product(extracted_data)
        confidence_score = self._calculate_confidence(
            extracted_product, category.attribute_schema
        )

        if confidence_score >= 0.8:
            status = "completed"
        elif confidence_score >= 0.5:
            status = "partial"
        else:
            status = "failed"

        # Handle auto-save if requested
        product_saved = False
        saved_product_id = None
        warnings = extracted_data.get("warnings", [])

        if save_product and status in ("completed", "partial"):
            try:
                saved_product_id = self._save_extracted_product(
                    extracted_product=extracted_product,
                    vendor_id=vendor_id,
                    category_id=category.id,
                    datasheet_url=url,
                )
                product_saved = True
            except ValueError as e:
                warnings.append(f"Auto-save failed: {str(e)}")

        return UrlExtractionResponse(
            extraction_id=extraction_id,
            source_type="html",
            source_url=url,
            status=status,
            confidence_score=confidence_score,
            extracted_product=extracted_product,
            warnings=warnings,
            vendor_created=vendor_created,
            product_saved=product_saved,
            saved_product_id=saved_product_id,
        )

    def _build_html_extraction_prompt(
        self, category: Category, text_content: str
    ) -> str:
        """Build extraction prompt for HTML text content."""
        schema = category.attribute_schema or {}
        schema_json = json.dumps(schema, indent=2)

        return f"""You are a product data extraction specialist. Extract structured
product information from the following web page content.

Target Category: {category.name}

Expected Attributes Schema:
{schema_json}

Web Page Content:
---
{text_content}
---

Instructions:
1. Extract all fields matching the schema from the page content
2. For each field, provide:
   - value: the extracted value (use exact types from schema)
   - confidence: "high", "medium", or "low"
   - source_note: brief note about where in content this was found
3. Mark missing fields as null with explanation in source_note
4. Normalize values to schema format/units:
   - Enums: use exact values from schema
   - Booleans: true/false
   - Numbers: numeric values only
   - Arrays: JSON arrays
5. Extract SKU, product name, and product family

Output as valid JSON with this exact structure:
{{
  "sku": "extracted SKU or null",
  "name": "product name or null",
  "product_family": "product line/series or null",
  "attributes": {{
    "attribute_key": {{
      "value": extracted_value_or_null,
      "confidence": "high|medium|low",
      "source_note": "where this was found or why it's missing"
    }}
  }},
  "warnings": ["list of any issues or notes"]
}}

Important: Return ONLY the JSON object, no additional text or markdown formatting."""

    def _find_pdf_links(self, html_content: str, base_url: str) -> list[PdfLink]:
        """Find PDF links in HTML content.

        Args:
            html_content: Raw HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of PdfLink objects
        """
        soup = BeautifulSoup(html_content, "html.parser")
        pdf_links = []
        seen_urls = set()

        # Find all anchor tags with PDF links
        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Check if it's a PDF link
            if not self._is_pdf_link(href):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)

            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Get title from link text or nearby content
            title = link.get_text(strip=True)
            if not title:
                title = link.get("title") or link.get("aria-label")

            pdf_links.append(PdfLink(url=full_url, title=title or None))

        return pdf_links

    def _is_pdf_link(self, href: str) -> bool:
        """Check if a link points to a PDF."""
        href_lower = href.lower()
        return (
            href_lower.endswith(".pdf")
            or "pdf" in href_lower
            or "/pdf/" in href_lower
        )

    def extract_batch_from_urls(
        self, request: BatchUrlExtractionRequest
    ) -> BatchUrlExtractionResponse:
        """Extract from multiple PDF URLs.

        Args:
            request: Batch extraction request with list of PDF URLs

        Returns:
            BatchUrlExtractionResponse with results for each URL
        """
        vendor_created = False

        # Validate category exists
        category = (
            self.db.query(Category)
            .filter(Category.id == request.category_id)
            .first()
        )
        if not category:
            raise ValueError(f"Category '{request.category_id}' not found")

        # Auto-create vendor if not exists
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == request.vendor_id)
            .first()
        )
        if not vendor:
            vendor = Vendor(
                id=request.vendor_id,
                name=request.vendor_id.replace("_", " ").title(),
            )
            self.db.add(vendor)
            self.db.commit()
            vendor_created = True

        results = []
        successful = 0
        failed = 0

        for pdf_url in request.pdf_urls:
            try:
                # Fetch PDF
                response = httpx.get(
                    pdf_url,
                    follow_redirects=True,
                    timeout=30.0,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; VARProductIntelligence/1.0)"
                    },
                )
                response.raise_for_status()

                # Extract
                extraction_id = str(uuid.uuid4())
                result = self._extract_from_pdf_url(
                    extraction_id=extraction_id,
                    url=pdf_url,
                    pdf_content=response.content,
                    category=category,
                    vendor_id=request.vendor_id,
                    vendor_created=False,  # Only count once
                    save_product=request.save_product,
                )

                results.append(
                    BatchExtractionResult(
                        url=pdf_url,
                        success=True,
                        extraction_id=result.extraction_id,
                        status=result.status,
                        confidence_score=result.confidence_score,
                        extracted_product=result.extracted_product,
                        warnings=result.warnings,
                        product_saved=result.product_saved,
                        saved_product_id=result.saved_product_id,
                    )
                )
                successful += 1

            except Exception as e:
                results.append(
                    BatchExtractionResult(
                        url=pdf_url,
                        success=False,
                        error=str(e),
                    )
                )
                failed += 1

        return BatchUrlExtractionResponse(
            total=len(request.pdf_urls),
            successful=successful,
            failed=failed,
            results=results,
            vendor_created=vendor_created,
        )
