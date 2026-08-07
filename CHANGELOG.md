# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-08-07

### Added

- `preview_data` MCP tool: inspect up to 100 rows of a query before
  committing to a full export.
- `export_data` MCP tool: write a full municipal panel to a local CSV or
  Parquet file instead of returning it into the model's context; the
  response is metadata only (row count, format, file path), with a
  200,000-record safety ceiling independent of the in-context limit.

### Changed

- Extracted the codes/years/municipios deduplication and
  region/municipios exclusivity check shared by `get_data`,
  `preview_data`, and `export_data` into `_normalize_query()`.
- Added `pyarrow` as a runtime dependency (Parquet support).

### Docs

- Clarified in `SECURITY.md` what a pre-1.0 (`0.x`) version number means.

## [0.2.0] - 2026-08-04

### Fixed

- `SINIMClient.get()` now filters the parsed response down to the
  requested years, the same way it already filtered municipios — a
  response spanning extra years could previously inflate `get_data`'s
  row count past its declared limit even though only one year was asked
  for. The MCP `get_data` tool also re-checks the actual response size
  after fetching, as a safety net on top of its pre-flight estimate.
- `mcp_sinim.parser` distinguishes a genuinely empty SINIM response from
  one whose SpreadsheetML no longer matches the expected `CODIGO`/year
  layout (`SpreadsheetSchemaError`), instead of silently returning `[]`
  for both.
- `HttpClient` retries `429` responses and honors `Retry-After`, with
  jittered exponential backoff and constructor validation.

### Added

- `SINIMClient.get()` rejects empty or unknown variable codes up front
  instead of silently returning blank names/units.
- MCP `search_municipalities` tool (fuzzy municipality search, previously
  only available on `SINIMClient`).
- MCP server lifespan: the shared HTTP client is now closed on server
  shutdown instead of leaking a never-closed lazy singleton.
- MCP `get_data`: `years` is now a required argument, the response cap
  dropped from 5000 to 1000 records, `region`/`municipios` are mutually
  exclusive, and the per-region size estimate uses a real municipality
  count instead of a flat upper bound.
- Weighted variable search (name/area/subarea/unit/source), exact
  code/name matches ranked first, a small curated alias dictionary
  (`ipp`, `fcm`, etc.), and `limit` bounds (1-100) on both search
  functions.
- CI: Pyright (advisory), coverage measurement (90% floor), a wheel
  build+install smoke test, and an advisory `pip-audit` step.
- Release: migrated `publish.yml` from a stored PyPI API token to
  Trusted Publishing (OIDC), added `twine check` and a pre-publish
  lint/test gate, pinned all GitHub Actions to commit SHAs, added
  `SECURITY.md` and Dependabot config.

### Changed

- `mcp_sinim.client` no longer exposes `_variables()` as the server's
  only way to read the catalog; added a public `variables()` method.
- Runtime dependencies (`fastmcp`, `httpx`, `pandas`, `rapidfuzz`) are
  now version-range pinned instead of unbounded.

## [0.1.0] - 2026-07-21

### Fixed

- Municipality filters now translate public legal CUT codes to SINIM's
  internal municipality ids and encode multiple selections correctly.
- Region filters accept official Chilean region codes in addition to SINIM's
  internal portal ids.

First public release.

### Added

- `SINIMClient`: `catalog()`, `search()`, `get()` (tidy long with `name`
  and `unit`, or wide), `municipios()`, `search_municipios()`, `years()`.
  Years and region ids discovered dynamically from the SINIM portal.
- Fuzzy search over the 480-variable catalog (rapidfuzz), accent- and
  case-insensitive. Catalog snapshot packaged for offline use.
- Optional metadata disk cache (`cache_dir`).
- FastMCP server (`mcp-sinim`) with six tools: `search_variables`,
  `get_variable_info`, `get_data`, `list_areas`, `list_municipios`,
  `list_years`. Oversized `get_data` queries (>5000 estimated records)
  are rejected with an actionable message.
- Courteous networking: >=0.5 s between requests, retries with
  exponential backoff, explicit timeouts.
- Offline test suite (respx + recorded fixtures), CI matrix 3.10-3.13,
  monthly catalog-refresh workflow.

### Validated

- `cod_municipio` (SINIM `idLegal`) matches the official SUBDERE CUT
  codes 1:1 for all 345 municipalities (Antártica 12202 has no
  municipality and is correctly absent). Safe to merge with Censo,
  CASEN and other CUT-keyed datasets.
- `corrmon=True` applies a uniform per-year CPI-style factor that
  re-expresses values in pesos of the most recent published year
  (checked live against nominal values for 2015/2020/2024).

### Security / robustness

- Invalid upstream responses (broken XML, malformed municipios JSON,
  missing form selects) raise actionable `SINIMError`s instead of
  silently returning empty data (independent code review).
- Empty `years`/`municipios`/`regiones` lists are rejected up front.
- XML parser honors the encoding declared in the document prolog.
