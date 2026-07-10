# mcp-sinim

🚧 **en desarrollo — v0.1**

Python client and MCP server for Chile's **SINIM** (Sistema Nacional de
Información Municipal, [datos.sinim.gov.cl](https://datos.sinim.gov.cl)):
~345 municipalities, 2000–2024, 480 variables across 9 areas (finance, HR,
education, health, social, territorial, gender, and more).

Part of the `mcp_*` family by Maykol Medrano (`mcp_bcrp`, `mcp_imf`,
`mcp_wbgapi360`).

## Status

This package is in early scaffolding (Phase 0). The public API described
below is stable in shape but not yet implemented — see `CLAUDE.md` for the
full specification and roadmap.

## Install

```bash
pip install mcp-sinim
```

## Quickstart — library

```python
from mcp_sinim import SINIMClient

client = SINIMClient()
client.catalog()                       # full 480-variable catalog
client.search("ingresos propios")      # fuzzy search over variables
client.get(["<code>"], years=[2020, 2021])
```

## Quickstart — MCP server

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sinim": {
      "command": "mcp-sinim"
    }
  }
}
```

Or via the Claude CLI:

```bash
claude mcp add sinim -- mcp-sinim
```

## Tools

| Tool | Description |
| --- | --- |
| `search_variables(query, area?)` | Fuzzy search over the variable catalog |
| `get_variable_info(code)` | Full metadata for a variable |
| `get_data(codes, years?, municipios?, region?, corrmon?)` | Municipal data table |
| `list_areas()` | Subject areas available |
| `list_municipios(region?)` | Municipalities, optionally by region |

## License

MIT
