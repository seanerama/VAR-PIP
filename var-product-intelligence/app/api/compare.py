"""Comparison API endpoints."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.dependencies import DbSession, CurrentUser
from app.schemas.compare import CompareRequest, CompareResponse
from app.services.comparison_service import ComparisonService

router = APIRouter()


@router.post("", response_model=CompareResponse)
async def create_comparison(
    request: CompareRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Generate a product comparison PDF.

    Provide 2-10 product IDs to compare. All products must be from the same category.

    Returns a comparison ID and URL to download the generated PDF.
    PDFs expire after 24 hours.
    """
    service = ComparisonService(db)

    try:
        result = service.create_comparison(request, prepared_by=user)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{comparison_id}/download")
async def download_comparison(
    comparison_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Download a comparison PDF.

    The PDF must have been previously generated via POST /compare.
    PDFs expire after 24 hours.
    """
    service = ComparisonService(db)
    filepath, is_expired = service.get_pdf_path(comparison_id)

    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Comparison PDF has expired. Please generate a new comparison.",
        )

    if filepath is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison '{comparison_id}' not found",
        )

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=f"comparison_{comparison_id}.pdf",
    )
