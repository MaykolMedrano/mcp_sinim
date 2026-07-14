# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - not yet tagged

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
