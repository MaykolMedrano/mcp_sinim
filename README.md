# mcp-sinim

**Pull Chilean municipal data from SINIM with a searchable catalog, tidy municipal panels, and the same package from Python or any MCP-compatible client.**

An open-source project by Maykol Medrano.

[![PyPI](https://img.shields.io/pypi/v/mcp-sinim.svg?style=flat-square&color=blue)](https://pypi.org/project/mcp-sinim/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![CI](https://img.shields.io/github/actions/workflow/status/MaykolMedrano/mcp_sinim/ci.yml?branch=main&style=flat-square)](https://github.com/MaykolMedrano/mcp_sinim/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

---

## What You Can Do

- Search roughly 480 SINIM variables by natural language instead of memorizing `id_dato` codes.
- Pull one or many municipal indicators as tidy `pandas` panels in one call.
- Discover available years and municipality codes directly from the live portal.
- Use the same package in notebooks, scripts, or MCP clients.
- Work with an offline catalog snapshot plus optional metadata caching.

## Installation

```bash
pip install mcp-sinim
```

## Python Example

```python
from mcp_sinim import SINIMClient

client = SINIMClient(corrmon=True)

# 1) Find the right variable code
hits = client.search("patentes municipales")
print(hits[["code", "name"]].head(3).to_string(index=False))

# 2) Pull a tidy municipal panel
df = client.get(
    ["4173", "1311"],
    years=[2024],
    municipios=["13101", "13114", "13119"],  # Santiago, Las Condes, Providencia
)
print(df.head().to_string(index=False))

# 3) Explore metadata when needed
print(client.years()[-5:])
print(client.search_municipios("providencia"))
```

Main things you will use:

- `search(...)` to find variable codes
- `get(...)` to pull municipal data
- `municipios(...)` and `search_municipios(...)` to work with legal municipality codes
- `years()` to see what is currently available

## MCP Server

Use `mcp-sinim` when you want an MCP client to search SINIM variables, inspect
their metadata, and fetch municipal data without writing a custom wrapper.

Run the server after installation:

```bash
mcp-sinim
```

Typical MCP configuration:

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

- `MCP_SINIM_CACHE_DIR` for the metadata disk cache

### MCP tools

| Tool | Description |
| :--- | :--- |
| `search_variables` | Search the SINIM variable catalog by keyword. |
| `get_variable_info` | Return metadata for one SINIM variable code. |
| `get_data` | Retrieve tidy municipal records for one or many variables. |
| `list_areas` | List the 9 catalog subject areas. |
| `list_municipios` | List municipalities, optionally filtered by region. |
| `list_years` | List currently available SINIM years. |

## Important Notes

- `cod_municipio` matches the official SUBDERE CUT codes for the 345 municipalities present in SINIM.
- `corrmon=True` requests SINIM's real-value series, expressed in pesos of the most recent published year.
- This is an independent open-source client for the public SINIM portal. It is not affiliated with SUBDERE or the Gobierno de Chile.

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
