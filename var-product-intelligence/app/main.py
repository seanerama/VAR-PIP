"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
from app.models.database import create_tables, get_db
from app.data.wireless_schema import ensure_wireless_category
from app.api import products, compare, categories, vendors, extract


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    create_tables()

    # Ensure wireless category exists
    db = next(get_db())
    try:
        ensure_wireless_category(db)
    finally:
        db.close()

    yield

    # Shutdown (nothing needed for now)


app = FastAPI(
    title="VAR Product Intelligence Platform",
    description="Product comparison and recommendation platform for Value-Added Resellers",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(compare.router, prefix="/compare", tags=["Comparison"])
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
app.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
app.include_router(extract.router, prefix="/extract", tags=["Extraction"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "VAR Product Intelligence Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
