"""Offline tests for :mod:`mcp_sinim.search_engine` (no network).

Searches run against the real packaged catalog (480 variables) so the
assertions double as a sanity check that fuzzy matching behaves sensibly
against production data, not just a toy fixture.
"""

from __future__ import annotations

import pandas as pd
import pytest

from mcp_sinim.catalog import packaged_catalog
from mcp_sinim.search_engine import MIN_SCORE, search_municipios, search_variables

VARIABLES = packaged_catalog()


# -- search_variables -------------------------------------------------------


def test_finds_patentes_municipales_in_top3() -> None:
    # A bare "patentes" matches 7+ variables that all contain the word
    # verbatim (Eficiencia Cobro Patentes Municipales, Patentes Mineras...),
    # so they tie on pure text similarity and code 4173 lands outside the
    # top-3 (it's still in the default top-10, see next test). A slightly
    # more specific, equally realistic query disambiguates deterministically.
    results = search_variables("patentes municipales", VARIABLES, limit=5)
    codes = [variable.code for variable, _score in results[:3]]
    assert "4173" in codes


def test_bare_patentes_query_still_returns_4173_within_default_limit() -> None:
    results = search_variables("patentes", VARIABLES, limit=10)
    codes = {variable.code for variable, _score in results}
    assert "4173" in codes


def test_ingresos_propios_returns_finanzas_results() -> None:
    results = search_variables("ingresos propios", VARIABLES, limit=5)
    assert results
    assert any("FINANZAS" in variable.area.upper() for variable, _score in results)


def test_accented_and_unaccented_queries_match_identically() -> None:
    with_accent = search_variables("educación", VARIABLES, limit=10)
    without_accent = search_variables("educacion", VARIABLES, limit=10)
    assert with_accent  # sanity: there are education variables to find
    assert [variable.code for variable, _score in with_accent] == [
        variable.code for variable, _score in without_accent
    ]


def test_area_filter_restricts_results() -> None:
    results = search_variables("gastos", VARIABLES, limit=10, area="finanzas")
    assert results
    assert all("FINANZAS" in variable.area.upper() for variable, _score in results)


def test_area_filter_matching_nothing_returns_empty() -> None:
    assert search_variables("gastos", VARIABLES, area="area que no existe") == []


def test_garbage_query_returns_empty_list() -> None:
    assert search_variables("zzxxqq nonsense gibberish 12345", VARIABLES) == []


def test_blank_query_returns_empty_list() -> None:
    assert search_variables("", VARIABLES) == []
    assert search_variables("   ", VARIABLES) == []


def test_results_are_sorted_descending_and_above_cutoff() -> None:
    results = search_variables("salud", VARIABLES, limit=10)
    scores = [score for _variable, score in results]
    assert scores  # non-empty
    assert scores == sorted(scores, reverse=True)
    assert all(score >= MIN_SCORE for score in scores)


def test_limit_is_respected() -> None:
    results = search_variables("municipal", VARIABLES, limit=3)
    assert len(results) <= 3


# -- search_municipios --------------------------------------------------------


@pytest.fixture
def municipios_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cod_municipio": ["13101", "13102", "05101", "08101"],
            "nombre_municipio": ["SANTIAGO", "CERRILLOS", "VALPARAISO", "CONCEPCION"],
        }
    )


def test_search_municipios_finds_best_match_first(municipios_df: pd.DataFrame) -> None:
    results = search_municipios("santiago", municipios_df, limit=5)
    assert "score" in results.columns
    assert results["nombre_municipio"].iloc[0] == "SANTIAGO"


def test_search_municipios_accent_insensitive() -> None:
    df = pd.DataFrame({"cod_municipio": ["05201"], "nombre_municipio": ["CONCEPCIÓN"]})
    assert len(search_municipios("concepcion", df)) == 1


def test_search_municipios_blank_query_returns_empty(municipios_df: pd.DataFrame) -> None:
    result = search_municipios("", municipios_df)
    assert result.empty
    assert "score" in result.columns


def test_search_municipios_empty_frame_returns_empty() -> None:
    empty = pd.DataFrame(columns=["cod_municipio", "nombre_municipio"])
    result = search_municipios("santiago", empty)
    assert result.empty


def test_search_municipios_garbage_query_returns_empty(municipios_df: pd.DataFrame) -> None:
    result = search_municipios("zzxxqq nonsense gibberish", municipios_df)
    assert result.empty
