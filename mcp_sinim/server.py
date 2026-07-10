"""FastMCP server exposing SINIM municipal data as MCP tools.

Run with ``mcp-sinim`` (console script) or ``python -m mcp_sinim``. Tool
docstrings are in English for consistency with the rest of the mcp_*
family (mcp_bcrp, mcp_imf, mcp_wbgapi360).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_sinim.client import SINIMClient

mcp = FastMCP("sinim")


def _get_client() -> SINIMClient:
    """Return the shared :class:`SINIMClient` instance used by the tools."""
    raise NotImplementedError


@mcp.tool
def search_variables(query: str, area: str | None = None) -> list[dict[str, Any]]:
    """Fuzzy-search SINIM variables by name, optionally filtered by area.

    Args:
        query: Free-text search term (e.g. "own revenue", "ingresos propios").
        area: Optional area name to restrict the search to.

    Returns:
        Matching variables, each with code, name, area, subarea, unit and
        source.
    """
    raise NotImplementedError


@mcp.tool
def get_variable_info(code: str) -> dict[str, Any]:
    """Get full metadata for a single SINIM variable code.

    Args:
        code: The SINIM variable code (``id_dato``).

    Returns:
        A dict with the variable's name, area, subarea, unit and source.
    """
    raise NotImplementedError


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
        codes: SINIM variable codes to fetch.
        years: Years to include. Defaults to all available years.
        municipios: Municipality codes/names to filter by. Defaults to all.
        region: Region id to filter by. Defaults to all regions.
        corrmon: Whether to apply monetary correction (real pesos).

    Returns:
        Tidy records with cod_municipio, nombre_municipio, anio, variable,
        name, value and unit.
    """
    raise NotImplementedError


@mcp.tool
def list_areas() -> list[str]:
    """List all SINIM subject areas (e.g. finance, education, health).

    Returns:
        The distinct area names present in the catalog.
    """
    raise NotImplementedError


@mcp.tool
def list_municipios(region: str | None = None) -> list[dict[str, Any]]:
    """List municipalities, optionally filtered by region.

    Args:
        region: Region id to filter by. Defaults to all regions.

    Returns:
        Municipalities, each with code, name and region.
    """
    raise NotImplementedError


def main() -> None:
    """Entry point for the ``mcp-sinim`` console script and ``python -m mcp_sinim``."""
    mcp.run()


if __name__ == "__main__":
    main()
