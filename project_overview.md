# VAR Product Intelligence Platform

## Overview

The VAR Product Intelligence Platform is an API-first tool designed for Value-Added Resellers (VARs) selling network equipment across multiple vendors. It solves a common pain point in pre-sales engineering: quickly comparing products from different manufacturers to match customer requirements.

Instead of manually digging through datasheets and spreadsheets, pre-sales engineers can query a unified product database, filter by technical specifications, and generate professional comparison PDFs in seconds.

## The Problem

Pre-sales engineers at VARs face a recurring challenge:

1. **Fragmented product data** — Specs live in vendor datasheets, distributor portals, and personal spreadsheets
2. **Time-consuming comparisons** — Comparing 3-4 products across vendors means opening multiple PDFs and manually building tables
3. **Inconsistent formatting** — Every vendor presents specs differently, making apples-to-apples comparisons difficult
4. **Outdated information** — Price lists and product lifecycles change frequently

## The Solution

This platform provides:

- **Unified product database** with a flexible schema that handles different product categories (wireless APs, firewalls, switches, routers, collaboration endpoints, servers)
- **Powerful filtering API** to query by any combination of specs, price range, vendor, and lifecycle status
- **PDF comparison generator** that outputs clean, customer-ready documents
- **AI-powered datasheet extraction** using Claude to automatically parse vendor PDFs and populate product records

## Key Features

### Multi-Category Support

The platform uses a flexible attribute schema that adapts to each product category:

| Category | Example Attributes |
|----------|-------------------|
| Wireless | WiFi generation, MIMO config, throughput, PoE requirements |
| Firewalls | Threat throughput, UTM features, session capacity |
| Switches | Port count/speed, PoE budget, stacking support |
| Routers | WAN interfaces, SD-WAN support, VPN capacity |
| Collaboration | Camera resolution, room size, platform support |
| Servers | Processor family, memory capacity, storage bays |

### Flexible Data Management

- **JSON seed files** for easy initial data entry and version control
- **Database storage** (SQLite for development, PostgreSQL for production)
- **Simple migration path** — start with JSON, import to database as usage grows

### Smart Filtering

Query products using any combination of:
- Category and vendor
- Price range (list price or your cost)
- Lifecycle status (active, end-of-sale, end-of-life)
- Any category-specific attribute (e.g., "WiFi 6E outdoor APs with 2.5G+ uplink under $1,500")

### PDF Comparison Output

Generate professional comparison documents that include:
- Side-by-side spec tables
- Pricing information (optional)
- Custom title and notes
- Clean, printer-friendly formatting

### AI Datasheet Extraction

Upload a vendor datasheet PDF and let Claude extract:
- Product name and SKU
- All technical specifications matching your category schema
- Confidence scores for each extracted field
- Warnings for missing or ambiguous data

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  FastAPI Application                  │
├──────────────────────────────────────────────────────┤
│  Endpoints:                                          │
│  • /products - CRUD, filtering, search               │
│  • /compare - Generate comparison PDFs               │
│  • /extract - AI-powered datasheet parsing           │
│  • /categories - Manage product schemas              │
│  • /vendors - Vendor management                      │
└──────────────────────────────────────────────────────┘
          │                    │
          ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│  SQLite/Postgres │  │  Anthropic API   │
│  Product Data    │  │  (Claude)        │
└──────────────────┘  └──────────────────┘
          ▲
          │
┌──────────────────┐
│  JSON Seed Files │
│  (Initial Data)  │
└──────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Framework | FastAPI | High-performance async API |
| Database | SQLite → PostgreSQL | Flexible storage with JSON attribute support |
| PDF Generation | ReportLab | Professional document output |
| AI/LLM | Anthropic Claude | Datasheet extraction |
| Authentication | API Keys | Simple, per-user access control |

## Use Cases

### 1. Quick Product Lookup

*"What Cisco wireless APs support WiFi 6E?"*

```bash
curl "http://localhost:8000/products?vendor=cisco&category=wireless" \
  --data-urlencode 'attribute_filters={"wifi_generation": "wifi6e"}'
```

### 2. Customer Requirements Matching

*"Customer needs an outdoor AP, budget under $1,200, must have 2.5G uplink minimum"*

```bash
curl "http://localhost:8000/products?category=wireless&max_price=1200" \
  --data-urlencode 'attribute_filters={"form_factor": "outdoor", "uplink_speed": ["2.5g", "5g", "10g"]}'
```

### 3. Competitive Comparison

*"Generate a comparison PDF for these three firewall models"*

```bash
curl -X POST "http://localhost:8000/compare" \
  -d '{"product_ids": ["id-1", "id-2", "id-3"], "title": "Firewall Comparison for Acme Corp"}'
```

### 4. Rapid Data Entry

*"Extract specs from this new Aruba datasheet"*

```bash
curl -X POST "http://localhost:8000/extract/datasheet" \
  -d '{"category_id": "wireless", "vendor_id": "aruba", "file_content": "base64...", "filename": "aruba-635.pdf"}'
```

## Getting Started

### Prerequisites

- Python 3.11+
- Anthropic API key (for datasheet extraction feature)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/var-product-intelligence.git
cd var-product-intelligence

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Seed initial data
curl -X POST "http://localhost:8000/admin/seed" -H "X-API-Key: your-key"

# Run the server
uvicorn app.main:app --reload
```

### API Documentation

Once running, visit `http://localhost:8000/docs` for interactive Swagger documentation.

## Data Management

### Adding Products via JSON

Edit files in `/data/products/` to add new products:

```json
{
  "category_id": "wireless",
  "products": [
    {
      "sku": "NEW-AP-001",
      "vendor_id": "cisco",
      "name": "New Access Point Model",
      "list_price": 999.00,
      "attributes": {
        "wifi_generation": "wifi7",
        "form_factor": "indoor"
      }
    }
  ]
}
```

Then re-run the seed endpoint to import.

### Adding Products via API

```bash
curl -X POST "http://localhost:8000/products" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "NEW-AP-001",
    "vendor_id": "cisco",
    "category_id": "wireless",
    "name": "New Access Point Model",
    "list_price": 999.00,
    "attributes": {"wifi_generation": "wifi7"}
  }'
```

### Adding Products via Datasheet Extraction

Upload a PDF and let Claude do the work:

```bash
curl -X POST "http://localhost:8000/extract/datasheet" \
  -H "X-API-Key: your-key" \
  -d '{"category_id": "wireless", "vendor_id": "cisco", "file_content": "...", "filename": "datasheet.pdf"}'
```

Review the extracted data, then POST to `/products` to save.

## Roadmap

### Current (MVP)
- [x] Design specification
- [ ] Core API implementation
- [ ] Product filtering
- [ ] PDF comparison generation
- [ ] AI datasheet extraction

### Future Enhancements
- Web UI for non-technical users
- User registration and role-based access
- Bulk CSV/Excel import
- Distributor API integrations (Ingram, TD Synnex)
- AI-powered recommendations ("Based on your requirements, we suggest...")
- Full proposal/quote generation
- Multi-tenant support for multiple VAR organizations

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

[MIT License](LICENSE)

---

Built for pre-sales engineers who'd rather close deals than compare datasheets.
