"""API key authentication utilities."""

import logging

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

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
    logger.info(f"Verifying API key: {api_key[:8] if api_key else 'None'}...")

    if not api_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    api_keys = settings.get_api_keys()
    logger.info(f"Available API keys (truncated): {[k[:8] + '...' for k in api_keys.keys()]}")

    if api_key not in api_keys:
        logger.warning(f"API key not found in valid keys. Provided: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    username = api_keys[api_key]
    logger.info(f"API key validated for user: {username}")
    return username


async def get_current_user(api_key: str | None = Security(api_key_header)) -> str:
    """FastAPI dependency to get the current authenticated user.

    Args:
        api_key: API key from header (injected by FastAPI)

    Returns:
        Username associated with the API key
    """
    return verify_api_key(api_key)
