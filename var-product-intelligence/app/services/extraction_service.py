"""AI-powered datasheet extraction service using Anthropic Claude."""

import base64
import json
import uuid
from typing import Any

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.vendor import Vendor
from app.models.category import Category
from app.schemas.extract import (
    ExtractionRequest,
    ExtractionResponse,
    ExtractedProduct,
    ExtractedField,
)


class ExtractionService:
    """Service for extracting product data from datasheets using Claude."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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

        return ExtractionResponse(
            extraction_id=extraction_id,
            status=status,
            confidence_score=confidence_score,
            extracted_product=extracted_product,
            warnings=extracted_data.get("warnings", []),
            vendor_created=vendor_created,
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
                    confidence=field_data.get("confidence", "low"),
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
