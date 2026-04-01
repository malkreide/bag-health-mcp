# Contributing to bag-health-mcp

## Development Setup

```bash
git clone https://github.com/malkreide/bag-health-mcp
cd bag-health-mcp
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit tests only (no network required)
pytest tests/ -m "not live" -v

# Including live API tests (requires network)
pytest tests/ -m live --timeout=30
```

## Adding a New Tool

1. Define a Pydantic input model
2. Add `@mcp.tool(description=...)` decorated async function
3. Write both mocked and live tests
4. Update README tool table

## Data Source

All data from BAG IDD API (`api.idd.bag.admin.ch`). No auth required.
Spec: `https://api.idd.bag.admin.ch/swagger-ui/api-doc.html`
