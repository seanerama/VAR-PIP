# VAR Product Intelligence Platform (VAR-PIP)

A product intelligence platform for Value-Added Resellers (VARs) that provides AI-powered product data extraction, comparison, and pricing management across multiple vendors.

## Features

### Product Data Management
- **Multi-vendor support**: Cisco, HPE, Dell, Juniper, Aruba, Fortinet, Meraki
- **Category organization**: Wireless, Compute, Networking, Security, Storage
- **Product database**: SQLite-backed storage with full CRUD operations

### AI-Powered Extraction
- **URL extraction**: Extract product data from vendor datasheets and spec sheets
- **PDF parsing**: AI-powered extraction from PDF documents
- **Structured output**: Normalized product schemas with specifications

### Product Comparison
- **Side-by-side comparison**: Compare products across vendors
- **Specification matching**: Intelligent spec comparison
- **PDF generation**: Export comparisons to PDF reports

### MCP Server Integration
Exposes tools via Model Context Protocol for AI assistant integration:
- `list_products` - Query and filter products
- `get_product` - Get detailed product information
- `compare_products` - Compare multiple products
- `extract_from_url` - Extract product data from URLs
- `sync_cisco_prices` - Sync prices from Cisco Commerce Catalog API
- `lookup_cisco_prices` - Real-time Cisco price lookups

## Project Structure

```
var-product-intelligence/
├── app/
│   ├── api/              # REST API endpoints
│   ├── models/           # SQLAlchemy database models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic services
│   ├── scripts/          # Utility scripts (seeding, etc.)
│   ├── mcp_server.py     # MCP server for AI integration
│   └── main.py           # FastAPI application entry
└── pyproject.toml        # Project dependencies
```

## Installation

```bash
cd var-product-intelligence
uv sync
```

## Running the MCP Server

```bash
cd var-product-intelligence
uv run python -m app.mcp_server
```

## Running the FastAPI Server

```bash
cd var-product-intelligence
uv run uvicorn app.main:app --reload
```

## Cisco Commerce Catalog API Integration

### Overview
Integration with Cisco Commerce Catalog Web Services (CCWS) API for real-time pricing and product information.

### Features (Planned)
- **Price Sync**: Bulk sync list prices from Cisco to local database
- **Real-time Lookup**: Query current prices without database storage
- **EOL Tracking**: End-of-Life date monitoring
- **Service Mapping**: Available support contracts for products

### Configuration
Requires Cisco API credentials in `~/cisco_connector/.env`:
```env
CISCO_CLIENT_ID=your_client_id
CISCO_CLIENT_SECRET=your_client_secret
CISCO_CCO_USERNAME=your_cco_username
CISCO_CCO_PASSWORD=your_cco_password
CISCO_PRICE_LIST=GLUS
```

### API Requirements
- Cisco Partner account with CCW access
- API app registered with **Resource Owner Password Credentials** grant type
- Access to Commerce Catalog Web Services API

### Status
**Pending**: Awaiting Cisco API Console configuration to enable Resource Owner Password Credentials grant type. Contact: partner-integrations@cisco.com

### MCP Tools

#### `sync_cisco_prices`
Sync prices from Cisco Commerce Catalog to database with rate limiting.

Parameters:
- `skus` (optional): Specific SKUs to sync, or sync all Cisco products
- `price_list`: Price list code (default: GLUS)
- `batch_size`: SKUs per request (default: 50)
- `delay_between_batches`: Seconds between batches (default: 2.0)
- `dry_run`: Preview without saving (default: false)

#### `lookup_cisco_prices`
Real-time price lookup without database storage.

Parameters:
- `skus`: List of SKUs to look up (max 50)
- `price_list`: Price list code (default: GLUS)
- `include_availability`: Include lead time info
- `include_eol`: Include End-of-Life dates

#### `list_cisco_price_lists`
Returns available Cisco price list codes (GLUS, GLEMEA, GLEURO, etc.)

## Price Lists

| Code | Region | Currency |
|------|--------|----------|
| GLUS | United States | USD |
| GLEMEA | EMEA | USD |
| GLEURO | Europe | EUR |
| GLCA | Canada | CAD |
| GLGB | United Kingdom | GBP |

## Development

### Database
SQLite database stored at `var-product-intelligence/products.db`

### Seeding Data
```bash
cd var-product-intelligence
uv run python -m app.scripts.seed
```

## License

Proprietary - Internal Use Only
