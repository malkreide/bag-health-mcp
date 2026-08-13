# Contributing to bag-health-mcp

**[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)**

Thank you for your interest in contributing! This server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

---

## Reporting Issues

Use [GitHub Issues](https://github.com/malkreide/bag-health-mcp/issues) to report bugs or request features.

Please include:
- Python version and OS
- Full error message or description of unexpected behaviour
- Steps to reproduce

---

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `feat: add new tool`
6. Push and open a Pull Request against `main`

The live tests hit the real BAG and Obsan endpoints and are excluded from the command in step 4. To run them:

```bash
PYTHONPATH=src pytest tests/ -m live --timeout=30
```

`--timeout` comes from `pytest-timeout`, installed with the `dev` extra (`pip install -e ".[dev]"`). Without it pytest aborts with `unrecognized arguments`, and a hanging endpoint blocks the run. A scheduled workflow (`.github/workflows/live.yml`) runs these daily, because a recorded fixture proves the shape of a response on its recording date — not that the source still answers that way today.

---

## Code Style

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Type hints required for all public functions
- Tests required for new tools (`tests/test_server.py`)
- Follow the existing MCP / Pydantic v2 patterns in `server.py`

---

## Data Source

This server uses the BAG Infectious Disease Dashboard (IDD) API — no authentication required:

| Source | Documentation |
|--------|--------------|
| BAG IDD API | [api.idd.bag.admin.ch](https://api.idd.bag.admin.ch) |
| Swagger Docs | [api.idd.bag.admin.ch/swagger-ui/api-doc.html](https://api.idd.bag.admin.ch/swagger-ui/api-doc.html) |

When adding new tools, follow the existing pattern: Pydantic input model, `@mcp.tool` decorated async function, mocked + live tests.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
