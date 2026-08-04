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

# Small, hand-curated starting point for common SINIM terminology. Keeping
# this mapping explicit makes alias behavior transparent and easy to test.
ALIASES: dict[str, list[str]] = {
    "ingresos propios": ["ipp", "ingresos propios permanentes"],
    "fondo comun municipal": ["fcm", "fondo comun municipal"],
    "matricula": ["alumnos", "estudiantes", "matricula"],
    "permisos de circulacion": ["permiso vehicular", "permisos circulacion"],
}


def _normalize(text: str) -> str:
    """Fold ``text`` to a case/accent-insensitive form for matching.

    Decomposes accented characters (NFKD) and drops the combining marks,
    then casefolds. No extra dependency: pure :mod:`unicodedata`.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.casefold().strip()


def _variable_aliases(variable: Variable) -> list[str]:
    """Return aliases activated by phrases in the canonical search text."""
    canonical_text = _normalize(f"{variable.name} {variable.subarea}")
    return [
        alias for phrase, terms in ALIASES.items() if phrase in canonical_text for alias in terms
    ]


def _variable_haystack(variable: Variable) -> str:
    """Build the broad, lower-weight search document for a variable."""
    aliases = _variable_aliases(variable)
    fields = (
        variable.name,
        variable.area,
        variable.subarea,
        variable.unit,
        variable.unit_name,
        variable.source,
        *aliases,
    )
    return _normalize(" ".join(fields))


def _validate_limit(limit: int) -> None:
    """Require a bounded, positive result limit."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")


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
    _validate_limit(limit)

    candidates = variables
    if area:
        normalized_area = _normalize(area)
        candidates = [v for v in candidates if normalized_area in _normalize(v.area)]

    normalized_query = _normalize(query)
    if not normalized_query or not candidates:
        return []

    exact_matches: list[tuple[Variable, float]] = []
    fuzzy_candidates: list[Variable] = []
    for variable in candidates:
        if normalized_query in {_normalize(variable.code), _normalize(variable.name)}:
            exact_matches.append((variable, 100.0))
        else:
            fuzzy_candidates.append(variable)

    if len(exact_matches) >= limit:
        return exact_matches[:limit]

    names = [_normalize(variable.name) for variable in fuzzy_candidates]
    broad_haystacks = [_variable_haystack(variable) for variable in fuzzy_candidates]
    name_matches = process.extract(normalized_query, names, scorer=fuzz.WRatio, limit=None)
    broad_matches = process.extract(
        normalized_query, broad_haystacks, scorer=fuzz.WRatio, limit=None
    )
    name_scores = {index: score for _choice, score, index in name_matches}
    broad_scores = {index: score for _choice, score, index in broad_matches}
    for index, variable in enumerate(fuzzy_candidates):
        alias_score = max(
            (fuzz.WRatio(normalized_query, alias) for alias in _variable_aliases(variable)),
            default=0.0,
        )
        broad_scores[index] = max(broad_scores[index], alias_score)
    fuzzy_matches = [
        (variable, 0.7 * name_scores[index] + 0.3 * broad_scores[index])
        for index, variable in enumerate(fuzzy_candidates)
        if 0.7 * name_scores[index] + 0.3 * broad_scores[index] >= MIN_SCORE
    ]
    fuzzy_matches.sort(key=lambda match: match[1], reverse=True)
    remaining = limit - len(exact_matches)
    return exact_matches + fuzzy_matches[:remaining]


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
    _validate_limit(limit)

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
