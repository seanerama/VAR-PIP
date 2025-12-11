# VAR Product Intelligence Platform

A FastAPI-based REST API and MCP server for Value-Added Resellers (VARs) to compare network equipment products across multiple vendors.

## Features

- **Product Management**: Full CRUD operations with flexible JSON attributes per category
- **Advanced Filtering**: Filter by vendor, price range, lifecycle status, JSON attributes, full-text search
- **AI-Powered Extraction**: Extract product specs from vendor datasheets (PDF/HTML) using Claude
  - Single product extraction from individual datasheets
  - Multi-product extraction from family/portfolio datasheets
  - Automatic PDF discovery from HTML listing pages
- **PDF Comparisons**: Generate professional side-by-side product comparison documents
- **MCP Server**: Expose all functionality as tools for LLMs (Claude Code, Claude Desktop)
- **Datasheet URL Tracking**: Store source datasheet URLs with products for reference
- **Pre-loaded Seed Data**: 524 products across 5 categories from 10 vendors (see [DEVICE_CATALOG.md](DEVICE_CATALOG.md))

## Supported Product Categories

| Category | Description | Key Attributes |
|----------|-------------|----------------|
| `wireless` | Wireless Access Points | WiFi generation, radio config, throughput, bands, PoE |
| `compute` | Servers & Compute Nodes | CPU, RAM, storage, GPU support, form factor |
| `firewall` | Firewalls & Security Appliances | Throughput, IPS, VPN, ports, form factor |
| `router` | Enterprise Routers | Throughput, WAN ports, routing protocols, SD-WAN |
| `switch` | Network Switches | Port count, speed, PoE budget, layer, stacking |

## Supported Vendors

| Vendor | Count | Products | Categories |
|--------|-------|----------|------------|
| **Cisco** | 204 | Catalyst wireless, UCS servers, Firepower, Catalyst/Nexus switches, 8000 routers | wireless, compute, firewall, switch, router |
| **Juniper** | 73 | EX/QFX switches, SRX firewalls, ACX/MX routers | switch, firewall, router |
| **Cisco Meraki** | 70 | MR/CW wireless, MS switches, MX firewalls | wireless, switch, firewall |
| **HPE Aruba Networking** | 50 | Aruba wireless APs, CX switches | wireless, switch |
| **Palo Alto Networks** | 36 | PA-series firewalls (PA-400 to PA-7500) | firewall |
| **Dell Technologies** | 27 | PowerEdge rack servers | compute |
| **HPE Instant On** | 23 | Instant On switches and wireless APs | switch, wireless |
| **Fortinet** | 20 | FortiGate firewalls (G-Series, F-Series) | firewall |
| **HPE** | 16 | ProLiant Gen11 servers (DL, ML, RL series) | compute |
| **Juniper Mist** | 5 | Mist wireless APs | wireless |

## Current Product Database

The seed database includes **524 products**:

| Category | Count | Examples |
|----------|-------|----------|
| Switches | 213 | Catalyst 9200/9300/9500/9600, Nexus 9000, Meraki MS, Aruba CX, Juniper EX/QFX |
| Firewalls | 113 | Palo Alto PA-series, Cisco Firepower, FortiGate, Meraki MX, Juniper SRX |
| Compute | 72 | Cisco UCS C/X-Series, Dell PowerEdge, HPE ProLiant Gen11 |
| Wireless | 66 | Catalyst 9100/Wi-Fi 7, Meraki MR/CW, Aruba 500-730 series, Juniper Mist |
| Routers | 60 | Cisco Catalyst 8000 series, Juniper ACX/MX |

For the complete product list, see [DEVICE_CATALOG.md](DEVICE_CATALOG.md).

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **ORM**: SQLAlchemy
- **AI**: Anthropic Claude API
- **PDF Processing**: PyMuPDF (fitz) for text extraction
- **PDF Generation**: ReportLab
- **MCP**: FastMCP

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Anthropic API key (for extraction features)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd var-product-intelligence

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Load seed data (524 products)
uv run python -m app.scripts.seed load
```

### Running the REST API

```bash
uv run uvicorn app.main:app --reload
```

Access the API docs at http://localhost:8000/docs

### Running the MCP Server

For use with Claude Code or Claude Desktop:

```bash
uv run python -m app.mcp_server
```

Or add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "var-products": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "/path/to/var-product-intelligence"
    }
  }
}
```

## Seed Data Management

The project includes a comprehensive seed data system with 524 pre-loaded products.

### Loading Seed Data

```bash
# Load seed data (skips existing products)
uv run python -m app.scripts.seed load

# Load seed data with fresh database
uv run python -m app.scripts.seed load --clear
```

### Exporting Seed Data

To export the current database to update the seed file:

```bash
uv run python -m app.scripts.seed export
```

This exports all vendors, categories, and products to `seed_data.json`.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /products` | List/filter products |
| `POST /products` | Create a product |
| `GET /products/{id}` | Get product details |
| `PUT /products/{id}` | Update a product |
| `DELETE /products/{id}` | Delete a product |
| `POST /extract/from-url` | Extract product from datasheet URL |
| `POST /extract/batch` | Batch extract from multiple PDFs |
| `POST /compare` | Generate PDF comparison |
| `GET /vendors` | List vendors |
| `GET /categories` | List categories |

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_products` | List/filter products |
| `get_product` | Get product by ID |
| `get_product_by_sku` | Find product by SKU |
| `search_products_by_attribute` | Search by attribute value |
| `extract_product_from_url` | AI extraction from URL |
| `extract_products_batch` | Batch extraction |
| `list_vendors` | List all vendors |
| `create_vendor` | Create a vendor |
| `list_categories` | List categories |
| `get_category_attributes` | Get filterable attributes |
| `compare_products` | Generate PDF comparison |
| `update_product_price` | Update pricing |
| `delete_product` | Delete a product |

## Configuration

Environment variables (`.env`):

```bash
# Database
DATABASE_URL=sqlite:///./var_products.db

# Anthropic API (required for extraction)
ANTHROPIC_API_KEY=sk-ant-...

# PDF Output
PDF_OUTPUT_DIR=./output
PDF_EXPIRY_HOURS=24

# API Keys (format: API_KEY_{USERNAME}=key)
API_KEY_ADMIN=your-admin-key
API_KEY_USER=your-user-key
```

## Authentication

All REST API endpoints require an API key header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/products
```

## Example: Extract Products from a Datasheet

### Single Product Extraction

```bash
curl -X POST http://localhost:8000/extract/from-url \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.cisco.com/.../datasheet.pdf",
    "category_id": "wireless",
    "vendor_id": "cisco",
    "save_product": true
  }'
```

### Multi-Product Extraction (Family Datasheets)

```bash
curl -X POST http://localhost:8000/extract/from-url \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.paloaltonetworks.com/.../product-summary-specsheet",
    "category_id": "firewall",
    "vendor_id": "palo_alto",
    "save_product": true,
    "extract_all_products": true
  }'
```

## Project Structure

```
var-product-intelligence/
├── app/
│   ├── main.py              # FastAPI app
│   ├── mcp_server.py        # MCP server
│   ├── config.py            # Settings
│   ├── api/                  # REST endpoints
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   │   └── extraction_service.py  # AI extraction
│   ├── scripts/              # CLI utilities
│   │   └── seed.py           # Seed data export/import
│   └── utils/                # Utilities
├── seed_data.json            # Pre-loaded product database
├── DEVICE_CATALOG.md         # Complete device inventory
├── pyproject.toml
├── .env.example
└── README.md
```

## License

MIT
