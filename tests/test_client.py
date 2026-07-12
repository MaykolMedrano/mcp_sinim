"""Offline tests for :class:`mcp_sinim.SINIMClient` (httpx mocked via respx).

No test in this module touches the network: ``respx.mock`` intercepts every
httpx request and fails loudly on any unmocked call.
"""

from __future__ import annotations

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


def _fx(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _fx_bytes() -> bytes:
    """Raw catalog payload used to mock a live `catalog(refresh=True)` call.

    Reused from `recon/` (the same evidence `data/catalog.json` was built
    from) instead of duplicating a ~480-variable fixture. Still offline:
    respx serves these bytes locally, no network is touched.
    """
    return RECON_CATALOG_RAW.read_bytes()


@pytest.fixture()
def client() -> SINIMClient:
    c = SINIMClient()
    # Tests never need courtesy delays.
    c._http.min_interval = 0.0
    c._http.backoff_factor = 0.0
    yield c
    c.close()


@respx.mock
def test_years_discovered_from_form(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    years = client.years()
    assert years == sorted(years)
    # Values recorded from the live form (2026-07): SINIM now reaches 2025,
    # which is exactly why year discovery must be dynamic.
    assert 2022 in years and 2025 in years
    assert len(years) >= 24
    # The year -> 1-based period index mapping must match the recorded form.
    assert client._year_map()[2024] == 25
    assert client._year_map()[2025] == 26


@respx.mock
def test_years_fallback_when_form_unparseable(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=b"<html></html>"))
    years = client.years()
    assert years[0] == 2000
    assert len(years) >= 24  # computed range fallback


@respx.mock
def test_municipios_single_region(client: SINIMClient) -> None:
    respx.post(MUNICIPIOS_URL).mock(
        return_value=httpx.Response(200, content=_fx("municipios_131.json"))
    )
    frame = client.municipios(region="131")
    assert list(frame.columns) == ["cod_municipio", "nombre_municipio"]
    assert (frame["cod_municipio"].str.len() == 5).all()
    assert "SANTIAGO" in set(frame["nombre_municipio"])
    assert len(frame) >= 50  # Region Metropolitana has 52 municipalities


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
    # name/unit come from the packaged catalog (variable 4173).
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
def test_get_unknown_year_raises_actionable_error(client: SINIMClient) -> None:
    respx.get(FORM_URL).mock(return_value=httpx.Response(200, content=_fx("form_periodos.html")))
    with pytest.raises(SINIMError, match="1999"):
        client.get("4173", years=[1999])


def test_catalog_returns_packaged_dataframe(client: SINIMClient) -> None:
    # Uses the packaged catalog (no `refresh`), so no network call at all --
    # no respx route is registered, and any HTTP call would fail loudly.
    frame = client.catalog()
    assert list(frame.columns) == ["code", "name", "area", "subarea", "unit", "source"]
    assert len(frame) == 480
    assert "4173" in set(frame["code"])


def test_catalog_caches_variables_in_memory(client: SINIMClient) -> None:
    assert client._catalog is None
    client.catalog()
    cached = client._catalog
    assert cached is not None
    client.catalog()  # second call must reuse the cache, not rebuild it
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
    assert (results["score"].diff().dropna() <= 0).all()  # descending
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
    # A fresh client must read the disk cache without any network call
    # (no other respx route is registered, so an HTTP request would fail).
    with SINIMClient(cache_dir=tmp_path) as c2:
        frame = c2.catalog()
    assert len(frame) == 480
    assert "4173" in set(frame["code"])


def test_corrupt_catalog_cache_falls_back_to_packaged(tmp_path: Path) -> None:
    (tmp_path / "catalog.json").write_text("{not valid json", encoding="utf-8")
    with SINIMClient(cache_dir=tmp_path) as c:
        frame = c.catalog()
    assert len(frame) == 480  # packaged snapshot, not the corrupted file


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
        assert route.call_count == 1  # served from disk, no second request
    pd.testing.assert_frame_equal(first, second)
    # The cache file must be clean UTF-8 with readable accents.
    text = (tmp_path / "municipios_131.json").read_text(encoding="utf-8")
    assert "Ñ" in text


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
    assert any("ÑUÑOA" in name.upper() for name in results["nombre_municipio"])


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
