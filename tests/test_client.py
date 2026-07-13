"""Offline tests for :class:`mcp_sinim.SINIMClient` with respx-mocked HTTP."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

from mcp_sinim._http import BASE_URL, HttpClient, SINIMError, browser_headers
from mcp_sinim.client import SINIMClient

FIXTURES = Path(__file__).parent / "fixtures"
RECON_CATALOG_RAW = Path(__file__).parent.parent / "recon" / "catalog_raw_2026-07-08.json"

FORM_URL = f"{BASE_URL}.php"
DATA_URL = f"{BASE_URL}/obtener_datos_municipales.php"
MUNICIPIOS_URL = f"{BASE_URL}/obtener_municipios.php"
CATALOG_URL = f"{BASE_URL}/obtener_datos_filtros.php"

ERROR_PAGE = b"<html><body><h1><em>!Error inesperado....</em></h1></body></html>"
_SPREADSHEET_NS = "urn:schemas-microsoft-com:office:spreadsheet"


def _fx(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _fx_bytes() -> bytes:
    """Raw catalog payload reused for live-refresh tests without network access."""
    return RECON_CATALOG_RAW.read_bytes()


def _workbook_xml(years: list[int], rows: list[tuple[str, str, list[str]]]) -> bytes:
    """Build a minimal SpreadsheetML workbook for offline client tests."""
    header_cells = "".join(f"<Cell><Data>{year}</Data></Cell>" for year in years)
    body_rows = "".join(
        "<Row>"
        f"<Cell><Data>{code}</Data></Cell>"
        f"<Cell><Data>{name}</Data></Cell>"
        + "".join(f"<Cell><Data>{value}</Data></Cell>" for value in values)
        + "</Row>"
        for code, name, values in rows
    )
    xml = (
        '<?xml version="1.0"?>'
        f'<Workbook xmlns="{_SPREADSHEET_NS}">'
        "<Worksheet><Table>"
        "<Row><Cell><Data>title</Data></Cell></Row>"
        "<Row><Cell><Data>note</Data></Cell></Row>"
        "<Row><Cell><Data>CODIGO</Data></Cell><Cell><Data>MUNICIPIO</Data></Cell>"
        f"{header_cells}</Row>"
        f"{body_rows}"
        "</Table></Worksheet></Workbook>"
    )
    return xml.encode("utf-8")


@pytest.fixture()
def client() -> SINIMClient:
    c = SINIMClient()
    c._http.min_interval = 0.0
    c._http.backoff_factor = 0.0
    yield c
    c.close()


@respx.mock
def test_years_discovered_from_form(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    years = client.years()
    assert years == sorted(years)
    assert 2022 in years and 2025 in years
    assert len(years) >= 24
    assert client._year_map()[2024] == 25
    assert client._year_map()[2025] == 26


@respx.mock
def test_years_fallback_when_form_unparseable(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=b"<html></html>"))
    years = client.years()
    assert years[0] == 2001
    assert years[-1] == _dt.date.today().year - 1


@respx.mock
def test_years_network_error_propagates(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        client.years()


@respx.mock
def test_years_supports_latin1_form_html(client: SINIMClient) -> None:
    html = (
        '<select id="periodos">'
        '<option value="3">A\xf1o 2002</option>'
        '<option value="2">A\xf1o 2001</option>'
        "</select>"
    ).encode("latin-1")
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=html))
    assert client.years() == [2001, 2002]
    assert client._year_map()[2001] == 2


@respx.mock
def test_municipios_single_region(client: SINIMClient) -> None:
    respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    frame = client.municipios(region="131")
    assert list(frame.columns) == ["cod_municipio", "nombre_municipio"]
    assert (frame["cod_municipio"].str.len() == 5).all()
    assert "SANTIAGO" in set(frame["nombre_municipio"])
    assert len(frame) >= 50


@respx.mock
def test_municipios_without_region_select_raises_actionable_error(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=b"<html></html>"))
    with pytest.raises(SINIMError, match="region ids"):
        client.municipios()


@respx.mock
@pytest.mark.parametrize(
    ("body", "match"),
    [
        (b"not json", "invalid municipios JSON"),
        (json.dumps(["broken"]).encode("utf-8"), "was not a JSON object"),
        (json.dumps({"textos": ["broken"]}).encode("utf-8"), "non-object row"),
        (
            json.dumps({"textos": [{"idLegal": None, "municipio": "BROKEN"}]}).encode("utf-8"),
            "invalid `idLegal`",
        ),
    ],
)
def test_municipios_invalid_payload_raises_actionable_error(
    client: SINIMClient, body: bytes, match: str
) -> None:
    respx.post(MUNICIPIOS_URL).mock(return_value=httpx.Response(200, content=body))
    with pytest.raises(SINIMError, match=match):
        client.municipios(region="131")


@respx.mock
def test_get_returns_tidy_panel(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(
        return_value=httpx.Response(200, content=_fx("data_4173_2022_2024.xml"))
    )
    frame = client.get("4173", years=[2022, 2023, 2024])
    assert list(frame.columns) == [
        "cod_municipio",
        "nombre_municipio",
        "anio",
        "code",
        "name",
        "value",
        "unit",
    ]
    assert len(frame) == 1035
    assert set(frame["code"]) == {"4173"}
    santiago_2024 = frame.query("cod_municipio == '13101' and anio == 2024").iloc[0]
    assert santiago_2024["value"] == 24768668.0
    assert santiago_2024["name"] == "Ingresos por Patentes Municipales de Beneficio Municipal"
    assert santiago_2024["unit"] == "M$"


@respx.mock
def test_get_unknown_code_gets_empty_metadata(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(
        return_value=httpx.Response(200, content=_fx("data_4173_2022_2024.xml"))
    )
    frame = client.get("99999", years=[2022])
    assert set(frame["name"]) == {""}
    assert set(frame["unit"]) == {""}


@respx.mock
def test_get_wide_pivots_by_code(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(
        return_value=httpx.Response(200, content=_fx("data_4173_2022_2024.xml"))
    )
    wide = client.get("4173", years=[2022], tidy=False)
    assert "4173" in wide.columns
    assert {"cod_municipio", "nombre_municipio", "anio"} <= set(wide.columns)


@respx.mock
def test_get_invalid_spreadsheet_raises_actionable_error(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(return_value=httpx.Response(200, content=b"not xml at all"))
    with pytest.raises(SINIMError, match="invalid SpreadsheetML"):
        client.get("4173", years=[2022])


@respx.mock
def test_get_valid_empty_spreadsheet_returns_empty_frame(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    respx.get(DATA_URL).mock(return_value=httpx.Response(200, content=_workbook_xml([2022], [])))
    frame = client.get("4173", years=[2022])
    assert frame.empty
    assert list(frame.columns) == [
        "cod_municipio",
        "nombre_municipio",
        "anio",
        "code",
        "name",
        "value",
        "unit",
    ]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"years": []}, "`years`"),
        ({"municipios": []}, "`municipios`"),
        ({"regiones": []}, "`regiones`"),
    ],
)
def test_get_rejects_empty_selection_lists(
    client: SINIMClient, kwargs: dict[str, list[int] | list[str]], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        client.get("4173", **kwargs)


@respx.mock
def test_get_unknown_year_raises_actionable_error(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    with pytest.raises(SINIMError, match="1999"):
        client.get("4173", years=[1999])


def test_catalog_returns_packaged_dataframe(client: SINIMClient) -> None:
    frame = client.catalog()
    assert list(frame.columns) == ["code", "name", "area", "subarea", "unit", "source"]
    assert len(frame) == 480
    assert "4173" in set(frame["code"])


def test_catalog_caches_variables_in_memory(client: SINIMClient) -> None:
    assert client._catalog is None
    client.catalog()
    cached = client._catalog
    assert cached is not None
    client.catalog()
    assert client._catalog is cached


@respx.mock
def test_catalog_refresh_fetches_live_catalog(client: SINIMClient) -> None:
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(200, content=_fx_bytes()))
    frame = client.catalog(refresh=True)
    assert len(frame) == 480
    assert "4173" in set(frame["code"])


def test_search_delegates_to_search_engine(client: SINIMClient) -> None:
    results = client.search("ingresos propios", limit=5)
    assert list(results.columns) == ["code", "name", "area", "subarea", "unit", "source", "score"]
    assert 0 < len(results) <= 5
    assert (results["score"].diff().dropna() <= 0).all()
    assert any("FINANZAS" in area.upper() for area in results["area"])


def test_search_garbage_query_returns_empty_frame(client: SINIMClient) -> None:
    results = client.search("zzxxqq nonsense gibberish 12345")
    assert results.empty
    assert list(results.columns) == ["code", "name", "area", "subarea", "unit", "source", "score"]


@respx.mock
def test_catalog_refresh_persists_to_cache_dir(tmp_path: Path) -> None:
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(200, content=_fx_bytes()))
    with SINIMClient(cache_dir=tmp_path) as c:
        c._http.min_interval = 0.0
        c.catalog(refresh=True)
    assert (tmp_path / "catalog.json").is_file()
    with SINIMClient(cache_dir=tmp_path) as c2:
        frame = c2.catalog()
    assert len(frame) == 480
    assert "4173" in set(frame["code"])


def test_corrupt_catalog_cache_falls_back_to_packaged(tmp_path: Path) -> None:
    (tmp_path / "catalog.json").write_text("{not valid json", encoding="utf-8")
    with SINIMClient(cache_dir=tmp_path) as c:
        frame = c.catalog()
    assert len(frame) == 480


@respx.mock
def test_municipios_cached_on_disk(tmp_path: Path) -> None:
    route = respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    with SINIMClient(cache_dir=tmp_path) as c:
        c._http.min_interval = 0.0
        first = c.municipios(region="131")
        assert route.call_count == 1
        assert (tmp_path / "municipios_131.json").is_file()
        second = c.municipios(region="131")
        assert route.call_count == 1
    pd.testing.assert_frame_equal(first, second)
    text = (tmp_path / "municipios_131.json").read_text(encoding="utf-8")
    assert "\u00d1" in text


@respx.mock
def test_corrupt_municipios_cache_is_refetched(tmp_path: Path) -> None:
    (tmp_path / "municipios_131.json").write_text("[broken", encoding="utf-8")
    route = respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    with SINIMClient(cache_dir=tmp_path) as c:
        c._http.min_interval = 0.0
        frame = c.municipios(region="131")
    assert route.call_count == 1
    assert len(frame) >= 50


@respx.mock
def test_search_municipios_is_accent_insensitive(client: SINIMClient) -> None:
    respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    results = client.search_municipios("nunoa", region="131", limit=5)
    assert "score" in results.columns
    assert any("\u00d1U\u00d1OA" in name.upper() for name in results["nombre_municipio"])


def test_public_exports() -> None:
    import mcp_sinim

    assert mcp_sinim.SINIMClient is SINIMClient
    assert mcp_sinim.SINIMError is SINIMError
    assert set(mcp_sinim.__all__) == {"SINIMClient", "SINIMError", "Variable", "__version__"}


@respx.mock
def test_error_page_raises_sinim_error(client: SINIMClient) -> None:
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(200, content=ERROR_PAGE))
    with pytest.raises(SINIMError, match="Error inesperado"):
        client._fetch_catalog_raw()


@respx.mock
def test_http_retries_5xx_then_succeeds() -> None:
    route = respx.get(FORM_URL)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(200, content=b"ok"),
    ]
    http = HttpClient(min_interval=0.0, backoff_factor=0.0)
    try:
        response = http.get(FORM_URL, headers=browser_headers())
        assert response.content == b"ok"
        assert route.call_count == 3
    finally:
        http.close()


@respx.mock
def test_http_gives_up_after_max_retries() -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(500))
    http = HttpClient(min_interval=0.0, backoff_factor=0.0, max_retries=3)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            http.get(FORM_URL, headers=browser_headers())
    finally:
        http.close()
