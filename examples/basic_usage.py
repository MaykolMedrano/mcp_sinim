"""Basic usage example for mcp_sinim (library mode, no MCP server needed).

Run with ``python examples/basic_usage.py``. The catalog steps work
offline; the data steps hit datos.sinim.gov.cl (courteously rate-limited).
"""

from __future__ import annotations

from mcp_sinim import SINIMClient


def main() -> None:
    client = SINIMClient(corrmon=False)

    # 1. Explore the catalog of 480 variables (offline: packaged snapshot).
    catalog = client.catalog()
    print(f"Catalog: {len(catalog)} variables\n{catalog.head()}\n")

    # 2. Fuzzy-search a variable by keyword (accent/case-insensitive).
    results = client.search("patentes municipales", limit=5)
    print(f"Search 'patentes municipales':\n{results[['code', 'name', 'score']]}\n")

    # 3. Years available (discovered dynamically from the SINIM portal).
    years = client.years()
    print(f"Years: {years[0]}-{years[-1]}\n")

    # 4. Fetch data: municipal business-license revenue, last 3 years.
    data = client.get("4173", years=years[-3:])
    santiago = data.query("cod_municipio == '13101'")
    print(f"Variable 4173, SANTIAGO:\n{santiago}\n")

    # 5. Municipalities of Región Metropolitana (region id 131).
    municipios = client.municipios(region="131")
    print(f"Región Metropolitana: {len(municipios)} municipalities")
    print(client.search_municipios("nunoa", region="131").head(3))

    client.close()


if __name__ == "__main__":
    main()
