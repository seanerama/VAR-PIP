"""Cisco pricing service - integrates with Cisco Commerce Catalog API.

Uses the cisco_catalog_mcp client to fetch real-time pricing from Cisco
and sync it to the VAR-PIP database with rate limiting.
"""

import asyncio
import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.cisco_pricing import (
    CiscoPriceInfo,
    CiscoPriceLookupRequest,
    CiscoPriceLookupResponse,
    CiscoPriceSyncItem,
    CiscoPriceSyncRequest,
    CiscoPriceSyncResponse,
)

# Add cisco_connector to path
CISCO_CONNECTOR_PATH = Path.home() / "cisco_connector" / "src"
if str(CISCO_CONNECTOR_PATH) not in sys.path:
    sys.path.insert(0, str(CISCO_CONNECTOR_PATH))

logger = logging.getLogger(__name__)


class CiscoPricingService:
    """Service for syncing prices from Cisco Commerce Catalog API."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self._client = None

    def _get_client(self):
        """Lazy-load Cisco catalog client."""
        if self._client is None:
            try:
                from cisco_catalog_mcp.client import CiscoCatalogClient
                from cisco_catalog_mcp.config import Settings

                # Load settings from cisco_connector's .env file
                cisco_env_file = Path.home() / "cisco_connector" / ".env"
                settings = Settings(_env_file=str(cisco_env_file))
                self._client = CiscoCatalogClient(settings)
                logger.info("Cisco Catalog client initialized")
            except ImportError as e:
                raise RuntimeError(
                    f"cisco_catalog_mcp not found. Ensure it's installed or path is correct: {e}"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Cisco client: {e}")
        return self._client

    async def lookup_prices(
        self, request: CiscoPriceLookupRequest
    ) -> CiscoPriceLookupResponse:
        """Look up prices for SKUs without saving to database.

        This is for real-time price checks, not bulk sync.
        """
        if len(request.skus) > 50:
            raise ValueError("Maximum 50 SKUs for real-time lookup")

        client = self._get_client()

        # Build attribute list based on options
        from cisco_catalog_mcp.constants import (
            AVAILABILITY_ATTRIBUTES,
            BASIC_ATTRIBUTES,
            EOL_ATTRIBUTES,
            PRICING_ATTRIBUTES,
        )

        attributes = PRICING_ATTRIBUTES + BASIC_ATTRIBUTES
        if request.include_availability:
            attributes += AVAILABILITY_ATTRIBUTES
        if request.include_eol:
            attributes += EOL_ATTRIBUTES

        try:
            results = await client.get_item_information(
                skus=request.skus,
                price_list=request.price_list,
                attributes=attributes,
            )
        except Exception as e:
            logger.error(f"Cisco API error: {e}")
            return CiscoPriceLookupResponse(
                price_list=request.price_list,
                total=len(request.skus),
                found=0,
                not_found=len(request.skus),
                items=[
                    CiscoPriceInfo(sku=sku, error=str(e))
                    for sku in request.skus
                ],
            )

        items = []
        found = 0
        not_found = 0

        for result in results:
            if "error" in result:
                items.append(CiscoPriceInfo(
                    sku=result.get("sku", "unknown"),
                    error=result["error"],
                ))
                not_found += 1
                continue

            # Parse price
            price = None
            price_str = result.get("list_price")
            if price_str:
                try:
                    price = float(price_str)
                    found += 1
                except (ValueError, TypeError):
                    not_found += 1

            items.append(CiscoPriceInfo(
                sku=result.get("sku"),
                description=result.get("description"),
                list_price=price,
                currency=result.get("currency"),
                product_type=result.get("product_type"),
                erp_family=result.get("erp_family"),
                web_orderable=result.get("web_orderable"),
                lead_time=result.get("lead_time"),
                stockable=result.get("stockable"),
                end_of_sale_date=result.get("end_of_sale_date"),
                last_date_of_support=result.get("last_date_of_support"),
            ))

        return CiscoPriceLookupResponse(
            price_list=request.price_list,
            total=len(request.skus),
            found=found,
            not_found=not_found,
            items=items,
        )

    async def sync_prices(
        self, request: CiscoPriceSyncRequest
    ) -> CiscoPriceSyncResponse:
        """Sync prices from Cisco to database with rate limiting.

        Processes SKUs in batches with delays to avoid rate limits.
        """
        started_at = datetime.now()
        warnings = []

        # Get SKUs to sync
        if request.skus:
            skus_to_sync = request.skus
        else:
            # Get all Cisco products from database
            cisco_products = (
                self.db.query(Product)
                .filter(Product.vendor_id == "cisco")
                .all()
            )
            skus_to_sync = [p.sku for p in cisco_products if p.sku]

            if not skus_to_sync:
                return CiscoPriceSyncResponse(
                    success=True,
                    price_list=request.price_list,
                    dry_run=request.dry_run,
                    total_requested=0,
                    found=0,
                    updated=0,
                    unchanged=0,
                    not_found=0,
                    errors=0,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    duration_seconds=0,
                    warnings=["No Cisco products found in database"],
                )

        logger.info(
            f"Starting Cisco price sync for {len(skus_to_sync)} SKUs "
            f"(batch_size={request.batch_size}, delay={request.delay_between_batches}s)"
        )

        client = self._get_client()

        # Build attribute list
        from cisco_catalog_mcp.constants import (
            BASIC_ATTRIBUTES,
            EOL_ATTRIBUTES,
            PRICING_ATTRIBUTES,
        )

        attributes = PRICING_ATTRIBUTES + BASIC_ATTRIBUTES
        if request.update_eol_info:
            attributes += EOL_ATTRIBUTES

        # Process in batches
        all_items = []
        found = 0
        updated = 0
        unchanged = 0
        not_found = 0
        errors = 0

        for i in range(0, len(skus_to_sync), request.batch_size):
            batch = skus_to_sync[i : i + request.batch_size]
            batch_num = (i // request.batch_size) + 1
            total_batches = (len(skus_to_sync) + request.batch_size - 1) // request.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} SKUs)")

            try:
                results = await client.get_item_information(
                    skus=batch,
                    price_list=request.price_list,
                    attributes=attributes,
                )
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                errors += len(batch)
                for sku in batch:
                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        action="error",
                        message=str(e),
                    ))
                continue

            # Process results
            for result in results:
                sku = result.get("sku")
                if not sku:
                    continue

                if "error" in result:
                    not_found += 1
                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        action="not_found",
                        message=result["error"],
                    ))
                    continue

                # Parse price
                new_price = None
                price_str = result.get("list_price")
                if price_str:
                    try:
                        new_price = float(price_str)
                    except (ValueError, TypeError):
                        pass

                if new_price is None:
                    not_found += 1
                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        action="not_found",
                        message="No price returned",
                    ))
                    continue

                found += 1

                # Look up product in database
                product = self.db.query(Product).filter(Product.sku == sku).first()

                if not product:
                    # SKU not in our database
                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        new_price=new_price,
                        currency=result.get("currency"),
                        action="not_found",
                        message="SKU not in VAR-PIP database",
                        lead_time=result.get("lead_time"),
                    ))
                    continue

                old_price = product.list_price_float

                # Check if price changed
                if old_price is not None and abs(old_price - new_price) < 0.01:
                    unchanged += 1
                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        old_price=old_price,
                        new_price=new_price,
                        currency=result.get("currency"),
                        action="unchanged",
                        lead_time=result.get("lead_time"),
                    ))
                else:
                    updated += 1

                    if not request.dry_run:
                        product.list_price = Decimal(str(new_price))

                        # Update EOL info if requested
                        if request.update_eol_info:
                            eos_date = result.get("end_of_sale_date")
                            if eos_date:
                                # Update lifecycle status based on EOL
                                product.lifecycle_status = "end_of_sale"

                    all_items.append(CiscoPriceSyncItem(
                        sku=sku,
                        old_price=old_price,
                        new_price=new_price,
                        currency=result.get("currency"),
                        action="updated",
                        eol_date=result.get("end_of_sale_date"),
                        lead_time=result.get("lead_time"),
                    ))

            # Rate limiting delay between batches
            if i + request.batch_size < len(skus_to_sync):
                logger.debug(f"Waiting {request.delay_between_batches}s before next batch")
                await asyncio.sleep(request.delay_between_batches)

        # Commit changes if not dry run
        if not request.dry_run and updated > 0:
            self.db.commit()
            logger.info(f"Committed {updated} price updates")

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return CiscoPriceSyncResponse(
            success=errors == 0,
            price_list=request.price_list,
            dry_run=request.dry_run,
            total_requested=len(skus_to_sync),
            found=found,
            updated=updated,
            unchanged=unchanged,
            not_found=not_found,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            items=all_items[:100],  # Limit response size
            warnings=warnings,
        )

    def sync_prices_sync(
        self, request: CiscoPriceSyncRequest
    ) -> CiscoPriceSyncResponse:
        """Synchronous wrapper for sync_prices."""
        return asyncio.run(self.sync_prices(request))

    def lookup_prices_sync(
        self, request: CiscoPriceLookupRequest
    ) -> CiscoPriceLookupResponse:
        """Synchronous wrapper for lookup_prices."""
        return asyncio.run(self.lookup_prices(request))
