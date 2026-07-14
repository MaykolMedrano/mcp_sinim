# mcp-sinim **Python client and MCP server for Chile's SINIM municipal data portal. Search ~480 variables, fetch municipal panels, and use the same package from Python or any MCP-compatible client.** [![PyPI](https://img.shields.io/pypi/v/mcp-sinim.svg?style=flat-square&color=blue)](https://pypi.org/project/mcp-sinim/) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org/downloads/) [![CI](https://img.shields.io/github/actions/workflow/status/MaykolMedrano/mcp_sinim/ci.yml?branch=main&style=flat-square)](https://github.com/MaykolMedrano/mcp_sinim/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

---

## What You Get

- Fuzzy variable discovery over the SINIM catalog, with accent- and case-insensitive search.
- High-level municipal data retrieval through `SINIMClient.get(...)`.
- Dynamic year and municipality discovery from the live SINIM portal.
- Packaged offline catalog, optional metadata cache, retries, and explicit timeouts.
- MCP tools for search, metadata lookup, municipal listings, and data extraction.

## Installation

```bash
pip install mcp-sinim
```

## Python API

```python
from mcp_sinim import SINIMClient

client = SINIMClient(corrmon=True)

# Search the catalog
hits = client.search("patentes municipales")
print(hits[["code", "name"]].head(3))

# Fetch a tidy municipal panel
df = client.get("4173", years=[2022, 2023, 2024])
print(df.query("cod_municipio == '13101'").tail(1))

# Browse metadata
print(client.years()[-5:])
print(client.municipios(region="131").head())
```

Main methods:

- `catalog()`
- `search(query, limit=10)`
- `get(codes, years=None, municipios=None, region=None, corrmon=None, tidy=True)`
- `municipios(region=None)`
- `search_municipios(query, region=None, limit=10)`
- `years()`

## MCP Server

### Run the server

After installation:

```bash
mcp-sinim
```

Typical MCP config:

```json
{
  "mcpServers": {
    "sinim": {
      "command": "mcp-sinim"
    }
  }
}
```

Optional environment variable:

- `MCP_SINIM_CACHE_DIR`: directory for the metadata disk cache

### MCP tools

| Tool | Description |
| :--- | :--- |
| `search_variables` | Search the SINIM variable catalog by keyword. |
| `get_variable_info` | Return metadata for one SINIM variable code. |
| `get_data` | Retrieve tidy municipal records for one or many variables. |
| `list_areas` | List the 9 catalog subject areas. |
| `list_municipios` | List municipalities, optionally filtered by region. |
| `list_years` | List currently available SINIM years. |

## Project Notes

### Official municipal codes

`cod_municipio` matches the official SUBDERE CUT codes for the 345 municipalities
present in SINIM, so merges with other CUT-keyed datasets are safe.

### Monetary correction

`corrmon=True` requests SINIM's real-value series, re-expressed in pesos of the
most recent published year.

### Unofficial client

This is an independent open-source client for the public SINIM portal. It is
not affiliated with SUBDERE or the Gobierno de Chile.

## Development

```bash
git clone https://github.com/MaykolMedrano/mcp_sinim
cd mcp_sinim
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
