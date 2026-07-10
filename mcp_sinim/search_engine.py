"""Fuzzy search over the SINIM variable and municipality catalogs.

Built on `rapidfuzz <https://github.com/rapidfuzz/RapidFuzz>`_ for fast,
dependency-light approximate string matching.
"""

from __future__ import annotations

import pandas as pd


def search_variables(catalog: pd.DataFrame, query: str, limit: int = 10) -> pd.DataFrame:
    """Fuzzy-search variables by name/area/subarea.

    Parameters
    ----------
    catalog:
        Catalog DataFrame as returned by
        :func:`mcp_sinim.catalog.load_catalog`.
    query:
        Free-text search term.
    limit:
        Maximum number of results.

    Returns
    -------
    pandas.DataFrame
        Subset of ``catalog`` ranked by fuzzy match score (descending).
    """
    raise NotImplementedError


def search_municipios(municipios: pd.DataFrame, query: str, limit: int = 10) -> pd.DataFrame:
    """Fuzzy-search municipalities by name.

    Parameters
    ----------
    municipios:
        Municipios DataFrame as returned by
        :meth:`mcp_sinim.client.SINIMClient.municipios`.
    query:
        Free-text search term.
    limit:
        Maximum number of results.

    Returns
    -------
    pandas.DataFrame
        Subset of ``municipios`` ranked by fuzzy match score (descending).
    """
    raise NotImplementedError
