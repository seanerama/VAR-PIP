"""FastAPI dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.utils.auth import get_current_user

# Type aliases for common dependencies
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[str, Depends(get_current_user)]
