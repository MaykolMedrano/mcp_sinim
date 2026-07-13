"""FastMCP server exposing SINIM municipal data as MCP tools.

Run with ``mcp-sinim`` (console script) or ``python -m mcp_sinim``. Tool
docstrings are in English for consistency with the rest of the mcp_*
family (mcp_bcrp, mcp_imf, mcp_wbgapi360).

Configuration (environment variables):

* ``MCP_SINIM_CACHE_DIR`` — optional directory for the client's metadata
  disk cache (catalog and municipios). Unset disables the disk cache.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
from fastmcp import FastMCP

from mcp_sinim.client import SINIMClient
from mcp_sinim.search_engine import search_variables as _search_variables

mcp = FastMCP("sinim")

#: Cap on the (estimated) number of records ``get_data`` may return.
#: Protects MCP clients — LLM context windows — from accidental
#: full-country, full-history dumps.
MAX_RECORDS = 5000

#: Comuna-count upper bounds used for the pre-flight estimate.
_ALL_MUNICIPIOS = 345
_MAX_REGION_MUNICIPIOS = 60  # largest region (Metropolitana) has 52

#: Shared client instance, created lazily by :func:`_get_client`.
_client_instance: SINIMClient | None = None


def _get_client() -> SINIMClient:
    """Return the shared :class:`SINIMClient` instance used by the tools."""
    global _client_instance
    if _client_instance is None:
        cache_dir = os.environ.get("MCP_SINIM_CACHE_DIR") or None
        _client_instance = SINIMClient(cache_dir=cache_dir)
    return _client_instance


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records (NaN becomes ``None``)."""
    safe = frame.astype(object).where(frame.notna(), None)
    return safe.to_dict(orient="records")


@mcp.tool
def search_variables(query: str, area: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Fuzzy-search SINIM variables by name, optionally filtered by area.

    Matching is accent- and case-insensitive ("educacion" also finds
    "Educación").

    Args:
        query: Free-text search term (e.g. "patentes municipales",
            "ingresos propios").
        area: Optional area-name filter, matched as a substring (e.g.
            "finanzas", "educacion").
        limit: Maximum number of results (default 10).

    Returns:
        Matching variables ranked by relevance, each with code, name, area,
        subarea, unit, source and score (0-100). Empty list if nothing
        matches.
    """
    client = _get_client()
    matches = _search_variables(query, client._variables(), limit=limit, area=area)
    return [
        {
            "code": variable.code,
            "name": variable.name,
            "area": variable.area,
            "subarea": variable.subarea,
            "unit": variable.unit,
            "source": variable.source,
            "score": round(score, 1),
        }
        for variable, score in matches
    ]


@mcp.tool
def get_variable_info(code: str) -> dict[str, Any]:
    """Get full metadata for a single SINIM variable code.

    Args:
        code: The SINIM variable code (``id_dato``), e.g. "4173".

    Returns:
        A dict with the variable's code, name, area, subarea, unit,
        unit_name and source.
    """
    client = _get_client()
    for variable in client._variables():
        if variable.code == str(code):
            return {
                "code": variable.code,
                "name": variable.name,
                "area": variable.area,
                "subarea": variable.subarea,
                "unit": variable.unit,
                "unit_name": variable.unit_name,
                "source": variable.source,
            }
    raise ValueError(
        f"Unknown SINIM variable code {code!r}. Use the search_variables tool to find valid codes."
    )


@mcp.tool
def get_data(
    codes: list[str],
    years: list[int] | None = None,
    municipios: list[str] | None = None,
    region: str | None = None,
    corrmon: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch municipal data for one or more SINIM variables.

    Args:
        codes: SINIM variable codes to fetch (find them with
            search_variables).
        years: Years to include (e.g. [2022, 2023]). Defaults to ALL
            available years — prefer passing an explicit list to keep the
            response small.
        municipios: Municipality legal codes to keep (e.g. ["13101"]).
            Defaults to all ~345 municipalities.
        region: Region id to filter by (see list_municipios). Defaults to
            all regions.
        corrmon: Whether to apply monetary correction (real pesos).
            Defaults to the server's client default (nominal).

    Returns:
        Tidy records with cod_municipio, nombre_municipio, anio, code,
        name, value and unit. A missing observation has value None.
        Queries estimated to exceed 5000 records are rejected up front —
        narrow them with explicit years, municipios or a region.
    """
    client = _get_client()
    year_count = len(years) if years else len(client.years())
    if municipios:
        muni_count = len(municipios)
    elif region:
        muni_count = _MAX_REGION_MUNICIPIOS
    else:
        muni_count = _ALL_MUNICIPIOS
    estimate = len(codes) * year_count * muni_count
    if estimate > MAX_RECORDS:
        raise ValueError(
            f"This query could return roughly {estimate} records, above the "
            f"{MAX_RECORDS}-record limit for MCP responses. Narrow it down: "
            "pass an explicit `years` list, a `municipios` list, a `region`, "
            "or fewer codes per call."
        )
    frame = client.get(
        codes,
        years=years,
        municipios=municipios,
        regiones=[region] if region else None,
        corrmon=corrmon,
    )
    return _records(frame)


@mcp.tool
def list_areas() -> list[str]:
    """List all SINIM subject areas (e.g. finance, education, health).

    Returns:
        The distinct area names present in the catalog, sorted.
    """
    client = _get_client()
    return sorted({variable.area for variable in client._variables() if variable.area})


@mcp.tool
def list_municipios(region: str | None = None) -> list[dict[str, Any]]:
    """List municipalities, optionally filtered by region.

    Args:
        region: Region id to filter by (e.g. "131" = Región
            Metropolitana). Defaults to all regions (~345 municipalities).

    Returns:
        Municipalities, each with cod_municipio (legal code) and
        nombre_municipio.
    """
    client = _get_client()
    return _records(client.municipios(region=region))


@mcp.tool
def list_years() -> list[int]:
    """List the years with data available in SINIM.

    Discovered dynamically from the SINIM form, so newly published years
    appear automatically.

    Returns:
        Available years, ascending (e.g. 2001..2025).
    """
    return _get_client().years()


def main() -> None:
    """Entry point for the ``mcp-sinim`` console script and ``python -m mcp_sinim``."""
    mcp.run()


if __name__ == "__main__":
    main()
