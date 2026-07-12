"""Fuzzy search over the SINIM variable and municipality catalogs.

Built on `rapidfuzz <https://github.com/rapidfuzz/RapidFuzz>`_ for fast,
dependency-light approximate string matching. Matching is accent- and
case-insensitive (see :func:`_normalize`) so ``"educacion"`` and
``"educación"`` rank identically.
"""

from __future__ import annotations

import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process

from mcp_sinim.catalog import Variable

#: Minimum RapidFuzz WRatio score (0-100) for a match to be returned. Chosen
#: to keep obviously-unrelated queries out of the results while still
#: tolerating typos and partial terms.
MIN_SCORE = 55.0


def _normalize(text: str) -> str:
    """Fold ``text`` to a case/accent-insensitive form for matching.

    Decomposes accented characters (NFKD) and drops the combining marks,
    then casefolds. No extra dependency: pure :mod:`unicodedata`.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.casefold().strip()


def _variable_haystack(variable: Variable) -> str:
    """Text a query is matched against: variable name + subarea."""
    return _normalize(f"{variable.name} {variable.subarea}")


def search_variables(
    query: str,
    variables: list[Variable],
    limit: int = 10,
    area: str | None = None,
) -> list[tuple[Variable, float]]:
    """Fuzzy-search variables by name/subarea, ranked by relevance.

    Parameters
    ----------
    query:
        Free-text search term. Matching is accent- and case-insensitive.
    variables:
        Catalog entries to search, e.g. from
        :func:`mcp_sinim.catalog.packaged_catalog`.
    limit:
        Maximum number of results.
    area:
        Optional area filter: a case-insensitive, accent-insensitive
        substring match against :attr:`Variable.area` (e.g. ``"finanzas"``
        matches ``"01.  ADMINISTRACION Y FINANZAS MUNICIPALES"``).

    Returns
    -------
    list[tuple[Variable, float]]
        ``(variable, score)`` pairs with ``score`` in ``[0, 100]``, sorted
        by score descending. Empty if the query is blank, no variable
        clears :data:`MIN_SCORE`, or the area filter matches nothing.
    """
    candidates = variables
    if area:
        normalized_area = _normalize(area)
        candidates = [v for v in candidates if normalized_area in _normalize(v.area)]

    normalized_query = _normalize(query)
    if not normalized_query or not candidates:
        return []

    haystacks = [_variable_haystack(v) for v in candidates]
    matches = process.extract(
        normalized_query,
        haystacks,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=MIN_SCORE,
    )
    return [(candidates[index], score) for _choice, score, index in matches]


def search_municipios(query: str, municipios_df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Fuzzy-search municipalities by name, ranked by relevance.

    Analogous to :func:`search_variables`, matching against the
    ``nombre_municipio`` column.

    Parameters
    ----------
    query:
        Free-text search term. Matching is accent- and case-insensitive.
    municipios_df:
        Municipios DataFrame as returned by
        :meth:`mcp_sinim.client.SINIMClient.municipios` (must have a
        ``nombre_municipio`` column).
    limit:
        Maximum number of results.

    Returns
    -------
    pandas.DataFrame
        Subset of ``municipios_df`` matching ``query`` (score above
        :data:`MIN_SCORE`), in relevance order, with an added ``score``
        column. Empty (same columns, plus ``score``) if the query is blank,
        the input is empty, or nothing clears the score cutoff.
    """
    empty = municipios_df.iloc[0:0].copy()
    empty["score"] = pd.Series(dtype=float)

    normalized_query = _normalize(query)
    if not normalized_query or municipios_df.empty:
        return empty

    names = municipios_df["nombre_municipio"].astype(str).tolist()
    haystacks = [_normalize(name) for name in names]
    matches = process.extract(
        normalized_query,
        haystacks,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=MIN_SCORE,
    )
    if not matches:
        return empty

    positions = [index for _choice, _score, index in matches]
    scores = [score for _choice, score, _index in matches]
    result = municipios_df.iloc[positions].copy()
    result["score"] = scores
    return result.reset_index(drop=True)
