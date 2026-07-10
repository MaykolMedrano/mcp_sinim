"""HTTP client for the SINIM API (datos.sinim.gov.cl).

Wraps the three documented endpoints (catalog, data, municipios) with
courteous networking (rate limiting, retries with exponential backoff,
explicit timeouts) and exposes tidy :class:`pandas.DataFrame` results. See
``CLAUDE.md`` for the full endpoint contract (headers, encodings, quirks).

Implementation note: network calls and XML/JSON parsing land in Phase 1.
This module currently only defines the public shape of :class:`SINIMClient`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class SINIMClient:
    """Client for the Sistema Nacional de Información Municipal (SINIM).

    Parameters
    ----------
    corrmon:
        Default monetary correction flag (``corrmon`` query param) applied
        to :meth:`get` calls that don't override it explicitly.
    cache_dir:
        Optional directory used to cache catalog/municipios responses on
        disk. ``None`` (default) disables caching.
    timeout:
        Request timeout, in seconds, applied to all HTTP calls.
    """

    def __init__(
        self,
        corrmon: bool = False,
        cache_dir: str | Path | None = None,
        timeout: float = 30,
    ) -> None:
        self.corrmon = corrmon
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.timeout = timeout

    def catalog(self) -> pd.DataFrame:
        """Return the full SINIM variable catalog.

        Returns
        -------
        pandas.DataFrame
            Columns: ``code``, ``name``, ``area``, ``subarea``, ``unit``,
            ``source`` — one row per variable (~480 rows).
        """
        raise NotImplementedError

    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        """Fuzzy-search the variable catalog.

        Parameters
        ----------
        query:
            Free-text search term (e.g. ``"ingresos propios"``).
        limit:
            Maximum number of results to return.

        Returns
        -------
        pandas.DataFrame
            Catalog rows matching ``query``, ranked by relevance.
        """
        raise NotImplementedError

    def get(
        self,
        codes: str | list[str],
        years: list[int] | None = None,
        municipios: list[str] | None = None,
        regiones: list[str] | None = None,
        corrmon: bool | None = None,
        tidy: bool = True,
    ) -> pd.DataFrame:
        """Fetch municipal data for one or more SINIM variables.

        Parameters
        ----------
        codes:
            One or more SINIM variable codes (``id_dato``).
        years:
            Years to fetch. Defaults to every year returned by
            :meth:`years`.
        municipios:
            Municipality codes/names to filter by. Defaults to all.
        regiones:
            Region codes to filter by. Defaults to all.
        corrmon:
            Overrides the client's default monetary correction flag for
            this call only.
        tidy:
            If ``True`` (default), return long/tidy format with one row
            per (municipio, year, variable). If ``False``, return the raw
            wide layout closer to the SINIM XML response.

        Returns
        -------
        pandas.DataFrame
            Tidy columns: ``cod_municipio``, ``nombre_municipio``, ``anio``,
            ``variable``, ``name``, ``value``, ``unit``.
        """
        raise NotImplementedError

    def municipios(self, region: str | None = None) -> pd.DataFrame:
        """Return municipalities, optionally filtered by region.

        Parameters
        ----------
        region:
            Region id (see ``CLAUDE.md`` for the id mapping) or ``None``
            for all regions.

        Returns
        -------
        pandas.DataFrame
            One row per municipality.
        """
        raise NotImplementedError

    def years(self) -> list[int]:
        """Return the years with data available in SINIM.

        The list is discovered dynamically from the SINIM form/header
        endpoint; it must never be hardcoded.
        """
        raise NotImplementedError
