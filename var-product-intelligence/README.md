# VAR Product Intelligence Platform

A FastAPI-based REST API and MCP server for Value-Added Resellers (VARs) to compare network equipment products across multiple vendors.

## Features

- **Product Management**: Full CRUD operations with flexible JSON attributes per category
- **Advanced Filtering**: Filter by vendor, price range, lifecycle status, JSON attributes, full-text search
- **AI-Powered Extraction**: Extract product specs from vendor datasheets (PDF/HTML) using Claude
- **PDF Comparisons**: Generate professional side-by-side product comparison documents
- **MCP Server**: Expose all functionality as tools for LLMs (Claude Code, Claude Desktop)

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **ORM**: SQLAlchemy
- **AI**: Anthropic Claude API
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

## Example: Extract and Save a Product

```bash
# Extract from Cisco datasheet with auto-save
curl -X POST http://localhost:8000/extract/from-url \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.cisco.com/.../datasheet.pdf",
    "category_id": "wireless_access_points",
    "vendor_id": "cisco",
    "save_product": true
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
│   └── utils/                # Utilities
├── pyproject.toml
├── .env.example
└── README.md
```

## License

MIT
