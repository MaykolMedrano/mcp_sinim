# Project status

Snapshot date: 2026-07-12

## Current state

`mcp-sinim` is functionally complete for the planned `v0.1` scope: a Python
library plus an MCP server for Chile's SINIM portal. At the implementation
checkpoint, the local repository was clean, the offline test suite was green
(`95` tests), `ruff` was clean, and the release artifacts had been audited.

## What is included in v0.1

- Python client: `SINIMClient(corrmon, cache_dir, timeout)`
- Catalog/search API: `catalog`, `search`, `get`, `municipios`,
  `search_municipios`, `years`
- MCP server tools: `search_variables`, `get_variable_info`, `get_data`,
  `list_areas`, `list_municipios`, `list_years`
- Packaged offline catalog, optional disk cache, retries/timeouts, and a
  guardrail that rejects oversized `get_data` requests
- Monthly catalog refresh workflow and release documentation

## Live validations completed

- `cod_municipio` matches the official SUBDERE CUT codes 1:1 for all
  345 municipalities in SINIM. Antártica (CUT `12202`) is correctly absent
  because it has no municipality.
- `corrmon=True` applies a uniform per-year correction factor that re-expresses
  values in pesos of the most recent published year. Live spot checks matched
  expected factors for 2015 (`x1.552`), 2020 (`x1.359`), and 2024 (`x1.035`).

## Release steps still pending

1. Push `main` to `github.com/MaykolMedrano/mcp_sinim`
2. Configure PyPI trusted publishing for the `pypi` environment
3. Remove the temporary `if: false` guard from `.github/workflows/publish.yml`
4. Tag `v0.1.0` and push the tag

## Where to look next

- `README.md`: user-facing install and usage guide
- `SPEC.md`: implementation contract and technical notes
- `RELEASE.md`: release procedure
