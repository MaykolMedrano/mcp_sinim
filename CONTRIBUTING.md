# Contributing

Thanks for your interest in `mcp-sinim`. This project follows the same
conventions as its siblings (`mcp_bcrp`, `mcp_imf`, `mcp_wbgapi360`).

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -e ".[dev]"
```

## Before opening a PR

```bash
ruff check .
ruff format --check .
pytest
```

All three must pass. CI runs the same checks on Python 3.10–3.13.

## Standards

- Tests must run offline against fixtures in `tests/fixtures/` — never hit
  `datos.sinim.gov.cl` in CI.
- Full type hints on public code.
- Use `httpx`, never `requests`.
- Parse XML with `xml.etree`/`lxml`, never regex.
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`), in English.

See `SPEC.md` for the complete specification.
