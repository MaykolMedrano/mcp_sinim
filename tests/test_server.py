"""Offline tests for the FastMCP server tools (:mod:`mcp_sinim.server`).

Tool functions are called directly (fastmcp's ``@mcp.tool`` returns the
original function); registration is checked through ``mcp.list_tools()``.
The network is mocked with respx and the recorded fixtures, exactly like
the client tests. No test touches datos.sinim.gov.cl.
"""

from __future__ import annotations

import math
from pathlib import Path

import httpx
import pytest
import respx

import mcp_sinim.server as server
from mcp_sinim._http import BASE_URL
from mcp_sinim.client import SINIMClient

FIXTURES = Path(__file__).parent / "fixtures"

FORM_URL = f"{BASE_URL}.php"
DATA_URL = f"{BASE_URL}/obtener_datos_municipales.php"
MUNICIPIOS_URL = f"{BASE_URL}/obtener_municipios.php"


def _fx(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture()
def fresh_client(monkeypatch: pytest.MonkeyPatch) -> SINIMClient:
    """Give the server a fresh shared client with no courtesy delays."""
    c = SINIMClient()
    c._http.min_interval = 0.0
    c._http.backoff_factor = 0.0
    monkeypatch.setattr(server, "_client_instance", c)
    yield c
    c.close()


async def test_all_tools_are_registered() -> None:
    tools = await server.mcp.list_tools()
    assert {
        "search_variables",
        "get_variable_info",
        "get_data",
        "list_areas",
        "list_municipios",
        "list_years",
    } <= {tool.name for tool in tools}


def test_search_variables_finds_patentes(fresh_client: SINIMClient) -> None:
    results = server.search_variables("patentes municipales", limit=5)
    assert 0 < len(results) <= 5
    assert "4173" in {r["code"] for r in results}
    assert all(
        set(r) == {"code", "name", "area", "subarea", "unit", "source", "score"} for r in results
    )
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_variables_area_filter(fresh_client: SINIMClient) -> None:
    results = server.search_variables("ingresos", area="finanzas")
    assert results
    assert all("FINANZAS" in r["area"].upper() for r in results)


def test_search_variables_garbage_returns_empty(fresh_client: SINIMClient) -> None:
    assert server.search_variables("zzxxqq gibberish 98765") == []


def test_get_variable_info_known_code(fresh_client: SINIMClient) -> None:
    info = server.get_variable_info("4173")
    assert info["name"] == "Ingresos por Patentes Municipales de Beneficio Municipal"
    assert info["unit"] == "M$"
    assert info["unit_name"] == "MILES DE PESOS"


def test_get_variable_info_unknown_code_is_actionable(fresh_client: SINIMClient) -> None:
    with pytest.raises(ValueError, match="search_variables"):
        server.get_variable_info("00000")


@respx.mock
def test_get_data_returns_json_safe_records(fresh_client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(
        return_value=httpx.Response(200, content=_fx("data_4173_2022_2024.xml"))
    )
    records = server.get_data(["4173"], years=[2022, 2023, 2024])
    assert len(records) == 1035
    assert set(records[0]) == {
        "cod_municipio",
        "nombre_municipio",
        "anio",
        "code",
        "name",
        "value",
        "unit",
    }
    santiago = next(r for r in records if r["cod_municipio"] == "13101" and r["anio"] == 2024)
    assert santiago["value"] == 24768668.0
    assert santiago["unit"] == "M$"
    # The 4 recorded blanks must be JSON-safe None, never NaN.
    missing = [r for r in records if r["value"] is None]
    assert len(missing) == 4
    assert not any(isinstance(r["value"], float) and math.isnan(r["value"]) for r in records)


@respx.mock
def test_get_data_rejects_oversized_queries(fresh_client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    # One code, all years (25), all 345 comunas -> ~8625 records: too big.
    # Rejected before any data request (only the form is ever fetched).
    with pytest.raises(ValueError, match="Narrow it down"):
        server.get_data(["4173"])


@respx.mock
def test_get_data_region_scope_passes_size_guard(fresh_client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(
        return_value=httpx.Response(200, content=_fx("data_4173_2022_2024.xml"))
    )
    # One region bounds the estimate (60 x 25 x 1 = 1500), so this runs.
    records = server.get_data(["4173"], region="131")
    assert records


def test_list_areas_returns_sorted_distinct(fresh_client: SINIMClient) -> None:
    areas = server.list_areas()
    assert areas == sorted(areas)
    assert len(areas) == 9
    assert any("FINANZAS" in a.upper() for a in areas)


@respx.mock
def test_list_municipios_single_region(fresh_client: SINIMClient) -> None:
    respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    rows = server.list_municipios(region="131")
    assert len(rows) >= 50
    assert {"cod_municipio", "nombre_municipio"} == set(rows[0])
    assert "SANTIAGO" in {r["nombre_municipio"] for r in rows}


@respx.mock
def test_list_years_uses_dynamic_discovery(fresh_client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    years = server.list_years()
    assert 2025 in years
    assert years == sorted(years)
