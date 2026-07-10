"""Basic usage example for mcp_sinim (library mode, no MCP server needed).

This is a scaffold: the calls below match the v0.1 public API contract but
will raise NotImplementedError until Phase 1+ fills in client.py,
catalog.py, parser.py and search_engine.py.
"""

from __future__ import annotations

from mcp_sinim import SINIMClient


def main() -> None:
    client = SINIMClient(corrmon=False)
    print(f"mcp_sinim client ready: {client!r}")

    # 1. Explore the catalog of ~480 variables.
    # catalog = client.catalog()
    # print(catalog.head())

    # 2. Fuzzy-search for a variable by keyword.
    # results = client.search("ingresos propios", limit=5)
    # print(results)

    # 3. Fetch data for one or more variable codes.
    # data = client.get(
    #     codes=["<code>"],
    #     years=[2020, 2021, 2022],
    #     regiones=["123"],  # Región Metropolitana
    #     tidy=True,
    # )
    # print(data)

    # 4. List municipalities in a region.
    # municipios = client.municipios(region="123")
    # print(municipios)


if __name__ == "__main__":
    main()
