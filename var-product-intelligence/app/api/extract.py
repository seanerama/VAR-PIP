"""Datasheet extraction API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, CurrentUser
from app.schemas.extract import ExtractionRequest, ExtractionResponse
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
