"""Datasheet extraction API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, CurrentUser
from app.schemas.extract import (
    ExtractionRequest,
    ExtractionResponse,
    UrlExtractionRequest,
    UrlExtractionResponse,
    BatchUrlExtractionRequest,
    BatchUrlExtractionResponse,
)
from app.services.extraction_service import ExtractionService

router = APIRouter()


@router.post("/datasheet", response_model=ExtractionResponse)
async def extract_from_datasheet(
    request: ExtractionRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Extract product data from a vendor datasheet PDF using AI.

    Upload a base64-encoded PDF datasheet and specify the category and vendor.
    The AI will extract product specifications and return structured data.

    If the vendor doesn't exist, it will be automatically created.

    The response includes:
    - Extracted product data with confidence scores
    - Overall extraction status (completed, partial, failed)
    - Any warnings about missing or uncertain data

    Note: This endpoint requires a valid Anthropic API key configured.
    """
    service = ExtractionService(db)

    try:
        result = service.extract_from_datasheet(request)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


@router.post("/from-url", response_model=UrlExtractionResponse)
async def extract_from_url(
    request: UrlExtractionRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Extract product data from a URL using AI.

    Provide a URL and the system will automatically detect the content type:

    1. **Direct PDF URL** - Downloads the PDF and extracts product data
    2. **HTML page with PDF links** - Returns a list of discovered PDFs for selection
    3. **HTML page with inline specs** - Extracts product data directly from the page

    The response `source_type` field indicates what was found:
    - `pdf`: Direct PDF extraction completed
    - `html`: HTML content extraction completed
    - `pdf_listing`: PDF links found on page - use /extract/batch endpoint with the URLs

    If the vendor doesn't exist, it will be automatically created.

    Note: This endpoint requires a valid Anthropic API key configured.
    """
    service = ExtractionService(db)

    try:
        result = service.extract_from_url(request)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


@router.post("/batch", response_model=BatchUrlExtractionResponse)
async def extract_batch_from_urls(
    request: BatchUrlExtractionRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Extract product data from multiple PDF URLs.

    Use this endpoint to process multiple PDFs at once, typically after
    getting a list of PDF links from the /extract/from-url endpoint.

    Each PDF is processed independently and results are returned for each URL.

    The response includes:
    - Total number of URLs processed
    - Count of successful and failed extractions
    - Individual results for each URL with extracted data or error messages

    If the vendor doesn't exist, it will be automatically created.

    Note: This endpoint requires a valid Anthropic API key configured.
    Processing multiple PDFs may take some time.
    """
    service = ExtractionService(db)

    try:
        result = service.extract_batch_from_urls(request)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch extraction failed: {str(e)}",
        )
