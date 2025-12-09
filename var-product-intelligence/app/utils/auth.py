"""API key authentication utilities."""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None) -> str:
    """Verify an API key and return the associated username.

    Args:
        api_key: The API key to verify

    Returns:
        Username associated with the API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    api_keys = settings.get_api_keys()

    if api_key not in api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_keys[api_key]


async def get_current_user(api_key: str | None = Security(api_key_header)) -> str:
    """FastAPI dependency to get the current authenticated user.

    Args:
        api_key: API key from header (injected by FastAPI)

    Returns:
        Username associated with the API key
    """
    return verify_api_key(api_key)
