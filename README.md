# mcp-sinim

[![CI](https://github.com/MaykolMedrano/mcp_sinim/actions/workflows/ci.yml/badge.svg)](https://github.com/MaykolMedrano/mcp_sinim/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/mcp-sinim/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python client and MCP server for Chile's **SINIM** (Sistema Nacional de
Información Municipal, [datos.sinim.gov.cl](https://datos.sinim.gov.cl)):
~345 municipalities, 2001–2025, 480 variables across 9 areas (finance, HR,
education, health, social, territorial, gender, and more).

One package, two entry doors:

- **Library** — `from mcp_sinim import SINIMClient`, tidy
  `pandas.DataFrame` results.
- **MCP server** — `mcp-sinim`, six tools any MCP client (Claude Desktop,
  Claude Code, …) can call.

Part of the `mcp_*` family by Maykol Medrano (`mcp_bcrp`, `mcp_imf`,
`mcp_wbgapi360`).

## Install

```bash
pip install mcp-sinim
```

## Quickstart — library

```python
from mcp_sinim import SINIMClient

client = SINIMClient()

# Fuzzy search over the 480-variable catalog (accent/case-insensitive).
client.search("patentes municipales")
#    code                                               name  ...  score
# 0  1310              Eficiencia Cobro Patentes Municipales  ...   90.0
# 1  1311                 Monto Patentes Municipales Pagadas  ...   90.0
# 2  4173  Ingresos por Patentes Municipales de Beneficio...  ...   90.0

# Fetch data: tidy long panel with variable metadata attached.
df = client.get("4173", years=[2022, 2023, 2024])
df.query("cod_municipio == '13101'")  # SANTIAGO
#   cod_municipio nombre_municipio  anio  code            name       value unit
#          13101         SANTIAGO  2024  4173  Ingresos por…  24768668.0   M$

# Wide format (one column per variable), several variables at once:
client.get(["4173", "1310"], years=[2024], tidy=False)

# Everything else:
client.catalog()                  # full catalog as a DataFrame
client.years()                    # available years, discovered dynamically
client.municipios(region="131")   # municipalities (131 = Metropolitana)
client.search_municipios("nunoa") # fuzzy, finds ÑUÑOA
```

Useful constructor options:

```python
SINIMClient(
    corrmon=True,          # monetary correction (real pesos) by default
    cache_dir="~/.sinim",  # disk cache for metadata (catalog, municipios)
    timeout=30,
)
```

The variable catalog ships with the package, so `catalog()` and `search()`
work offline; `catalog(refresh=True)` re-fetches it live and, with
`cache_dir` set, persists it for later sessions.

## Quickstart — MCP server

With the Claude CLI:

```bash
claude mcp add sinim -- mcp-sinim
```

Or add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sinim": {
      "command": "mcp-sinim"
    }
  }
}
```

Optional environment variable: `MCP_SINIM_CACHE_DIR` — directory for the
metadata disk cache.

### Tools

| Tool | Description |
| --- | --- |
| `search_variables(query, area?, limit?)` | Fuzzy search over the variable catalog (accent-insensitive), ranked by relevance |
| `get_variable_info(code)` | Full metadata for one variable code |
| `get_data(codes, years?, municipios?, region?, corrmon?)` | Tidy municipal data records (JSON-safe, missing = `null`) |
| `list_areas()` | The 9 subject areas in the catalog |
| `list_municipios(region?)` | Municipalities with legal codes, optionally by region |
| `list_years()` | Years with published data, discovered dynamically |

### Areas

| # | Area |
| --- | --- |
| 01 | Administración y finanzas municipales |
| 02 | Recursos humanos municipal |
| 03 | Educación municipal |
| 04 | Salud municipal |
| 05 | Social y comunitaria |
| 06 | Desarrollo y gestión territorial |
| 07 | Caracterización comunal |
| 08 | Género |
| 09 | Cementerio |

## Notes

- Data comes from the public SINIM portal of SUBDERE (Gobierno de Chile);
  this project is not affiliated with SUBDERE.
- The client is polite to the server: ≥0.5 s between requests, retries
  with exponential backoff, explicit timeouts.
- Available years and region ids are discovered dynamically from the
  portal, so newly published years appear without a package update.
- `examples/` has a runnable script and a user-guide notebook.

## Development

```bash
git clone https://github.com/MaykolMedrano/mcp_sinim
cd mcp_sinim
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest  # all offline, no network
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [RELEASE.md](RELEASE.md).

## License

[MIT](LICENSE)
