"""HTTP client for the SINIM API (datos.sinim.gov.cl).

Wraps the documented endpoints (form/years, data, municipios, catalog) on
top of :mod:`mcp_sinim._http` (courteous networking) and
:mod:`mcp_sinim.parser` (XML SpreadsheetML -> tidy records), exposing tidy
:class:`pandas.DataFrame` results. See ``CLAUDE.md`` for the endpoint
contract (headers, encodings, quirks).

Metadata (catalog, municipios) can additionally be cached on disk via the
``cache_dir`` constructor argument; data fetches (:meth:`SINIMClient.get`)
always hit the network.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pandas as pd

from mcp_sinim._http import BASE_URL, HttpClient, SINIMError, browser_headers, data_headers
from mcp_sinim.catalog import (
    CATALOG_FIELDS,
    Variable,
    build_catalog,
    load_catalog,
    packaged_catalog,
    save_catalog,
)
from mcp_sinim.parser import parse_spreadsheet_xml
from mcp_sinim.search_engine import search_municipios, search_variables

#: Columns of the DataFrame returned by :meth:`SINIMClient.catalog` (the
#: catalog's own ``unit_name`` field is left out to match the public
#: contract in ``CLAUDE.md``).
_CATALOG_DF_COLUMNS = [c for c in CATALOG_FIELDS if c != "unit_name"]

#: Endpoint URLs.
_FORM_URL = f"{BASE_URL}.php"
_DATA_URL = f"{BASE_URL}/obtener_datos_municipales.php"
_MUNICIPIOS_URL = f"{BASE_URL}/obtener_municipios.php"
_CATALOG_URL = f"{BASE_URL}/obtener_datos_filtros.php"

#: Matches ``<option value="N">Año YYYY</option>`` in the periodos select.
_PERIODO_RE = re.compile(r'<option[^>]*value="(\d+)"[^>]*>\s*A[nñ]o\s*(\d{4})', re.IGNORECASE)
#: Isolates the ``regiones`` ``<select>`` block from the form HTML.
_REGION_SELECT_RE = re.compile(r'<select[^>]*id="regiones".*?</select>', re.IGNORECASE | re.DOTALL)
#: Matches ``<option value="ID">NAME</option>`` (numeric region ids only).
_REGION_OPT_RE = re.compile(r'<option[^>]*value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>')
#: First calendar year SINIM publishes (index base for the fallback path).
_FIRST_YEAR = 2000


class SINIMClient:
    """Client for the Sistema Nacional de Información Municipal (SINIM).

    Parameters
    ----------
    corrmon:
        Default monetary correction flag (``corrmon`` query param) applied
        to :meth:`get` calls that don't override it explicitly.
    cache_dir:
        Optional directory used to cache metadata (catalog and municipios)
        responses on disk, so subsequent client instances can reuse them
        without hitting the network. ``None`` (default) disables the disk
        cache entirely (metadata still gets an in-memory cache for the
        lifetime of this instance). Never used for :meth:`get` data — those
        calls always hit the network. The directory is created lazily, on
        the first cache write. A corrupted cache file is ignored (falls
        back to the normal fetch path) rather than raising.
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
        self._http = HttpClient(timeout=timeout)
        # Cached form-derived lookups (discovered lazily from the form HTML).
        self._year_index: dict[int, int] | None = None
        self._regiones: dict[str, str] | None = None
        # In-memory catalog cache (see `catalog()`/`_variables()`).
        self._catalog: list[Variable] | None = None

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._http.close()

    def __enter__(self) -> SINIMClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- catalog -------------------------------------------------------------

    def catalog(self, refresh: bool = False) -> pd.DataFrame:
        """Return the full SINIM variable catalog.

        Parameters
        ----------
        refresh:
            If ``True``, re-fetch the catalog live from
            ``obtener_datos_filtros.php`` (via :meth:`_fetch_catalog_raw`)
            instead of using the packaged snapshot. The result — either the
            packaged snapshot or a live refresh — is cached in memory for
            subsequent calls (including :meth:`search`) until the client is
            recreated or ``refresh=True`` is passed again.

            With ``cache_dir`` set, a live refresh is also persisted to
            ``cache_dir/catalog.json``, and later calls (from this or a new
            client) prefer that file over the packaged snapshot. A missing
            or unreadable cache file falls back to the packaged snapshot.

        Returns
        -------
        pandas.DataFrame
            Columns: ``code``, ``name``, ``area``, ``subarea``, ``unit``,
            ``source`` — one row per variable (~480 rows).
        """
        return self._catalog_frame(self._variables(refresh=refresh))

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
            Catalog rows matching ``query``, ranked by relevance
            (descending), with an added ``score`` column (0-100). Empty if
            nothing matches.
        """
        matches = search_variables(query, self._variables(), limit=limit)
        frame = self._catalog_frame([variable for variable, _score in matches])
        frame["score"] = [score for _variable, score in matches]
        return frame

    def search_municipios(
        self, query: str, region: str | None = None, limit: int = 10
    ) -> pd.DataFrame:
        """Fuzzy-search municipalities by name.

        Parameters
        ----------
        query:
            Free-text search term. Matching is accent- and case-insensitive
            (``"nunoa"`` finds ``ÑUÑOA``).
        region:
            Optional region id restricting the search (see
            :meth:`municipios`). ``None`` searches every municipality.
        limit:
            Maximum number of results to return.

        Returns
        -------
        pandas.DataFrame
            Rows of :meth:`municipios` matching ``query``, ranked by
            relevance (descending), with an added ``score`` column (0-100).
            Empty if nothing matches.
        """
        return search_municipios(query, self.municipios(region=region), limit=limit)

    def _variables(self, refresh: bool = False) -> list[Variable]:
        """Return (and cache) the catalog as a list of :class:`Variable`.

        Resolution order: live fetch when ``refresh`` (persisted to the
        disk cache when ``cache_dir`` is set), else the in-memory cache,
        else the disk cache (``cache_dir/catalog.json``), else the packaged
        snapshot.
        """
        if refresh:
            self._catalog = build_catalog(self._fetch_catalog_raw())
            if self.cache_dir is not None:
                save_catalog(self._catalog, self.cache_dir / "catalog.json")
        elif self._catalog is None:
            self._catalog = self._cached_catalog() or packaged_catalog()
        return self._catalog

    def _cached_catalog(self) -> list[Variable] | None:
        """Load the disk-cached catalog; ``None`` if absent or unreadable."""
        if self.cache_dir is None:
            return None
        path = self.cache_dir / "catalog.json"
        if not path.is_file():
            return None
        try:
            return load_catalog(path)
        except (json.JSONDecodeError, OSError, TypeError, KeyError):
            return None

    @staticmethod
    def _catalog_frame(variables: list[Variable]) -> pd.DataFrame:
        """Convert a list of :class:`Variable` to the public catalog DataFrame."""
        records = [
            {field: getattr(variable, field) for field in _CATALOG_DF_COLUMNS}
            for variable in variables
        ]
        return pd.DataFrame(records, columns=_CATALOG_DF_COLUMNS)

    def _fetch_catalog_raw(self) -> dict:
        """Fetch the raw variable-catalog JSON from ``obtener_datos_filtros.php``.

        Returns
        -------
        dict
            The server's JSON payload: a mapping of subarea name to a list
            of variable metadata dicts (``id_dato`` is the variable code).
        """
        response = self._http.post(
            _CATALOG_URL,
            headers=browser_headers(),
            data={"dato_area[]": "T", "dato_subarea[]": "T"},
        )
        return json.loads(response.content.decode("utf-8"))

    # -- years -------------------------------------------------------------

    def years(self) -> list[int]:
        """Return the years with data available in SINIM.

        Discovered dynamically from the ``datos_municipales.php`` form (the
        ``periodos`` ``<select>``) and cached in memory. Falls back to
        ``range(2000, current_year)`` if the form cannot be parsed.
        """
        return sorted(self._year_map())

    def _year_map(self) -> dict[int, int]:
        """Return (and cache) the ``year -> 1-based period index`` mapping."""
        if self._year_index is None:
            self._year_index = self._discover_year_map()
        return self._year_index

    def _form_html(self) -> str:
        """Fetch the ``datos_municipales.php`` form HTML (UTF-8 text)."""
        response = self._http.get(_FORM_URL, headers=browser_headers())
        return response.content.decode("utf-8", errors="replace")

    def _discover_year_map(self) -> dict[int, int]:
        """Parse the form's periodos select; fall back to a computed range."""
        try:
            mapping = {
                int(year): int(index) for index, year in _PERIODO_RE.findall(self._form_html())
            }
        except Exception:  # noqa: BLE001 - fall back to computed range on any failure
            mapping = {}
        if mapping:
            return mapping
        # Fallback: SINIM period index is (year - 1999); no reliable top year.
        current = _dt.date.today().year
        return {year: year - (_FIRST_YEAR - 1) for year in range(_FIRST_YEAR, current)}

    def _region_ids(self) -> dict[str, str]:
        """Return (and cache) the ``region id -> name`` mapping from the form.

        The ids are discovered dynamically because CLAUDE.md's hardcoded
        list is outdated (e.g. Metropolitana is ``131``, not ``123``).
        """
        if self._regiones is None:
            block = _REGION_SELECT_RE.search(self._form_html())
            self._regiones = (
                {rid: name for rid, name in _REGION_OPT_RE.findall(block.group(0))} if block else {}
            )
        return self._regiones

    def _period_index(self, year: int) -> int:
        """Map a calendar year to its SINIM 1-based period index."""
        mapping = self._year_map()
        try:
            return mapping[year]
        except KeyError as exc:
            available = ", ".join(str(y) for y in sorted(mapping))
            raise SINIMError(
                f"Year {year} is not available in SINIM. Available years: {available}."
            ) from exc

    # -- municipios --------------------------------------------------------

    def municipios(self, region: str | None = None) -> pd.DataFrame:
        """Return municipalities, optionally filtered by region.

        Parameters
        ----------
        region:
            Region id (see the form's region select; e.g. ``"131"`` =
            Metropolitana). ``None`` (default) returns every municipality by
            querying each discovered region — the endpoint rejects the
            ``"T"`` (all) shortcut for this call.

            With ``cache_dir`` set, each region's response is cached on
            disk (``cache_dir/municipios_{region}.json``) and reused on
            later calls instead of hitting the network; a corrupted cache
            file is ignored and refetched.

        Returns
        -------
        pandas.DataFrame
            Columns ``cod_municipio`` (legal INE code) and
            ``nombre_municipio``, sorted by code.
        """
        if region is None:
            region_ids = list(self._region_ids())
        else:
            region_ids = [str(region)]

        rows: list[dict[str, str]] = []
        for region_id in region_ids:
            rows.extend(self._fetch_municipios(region_id))

        frame = pd.DataFrame(rows, columns=["cod_municipio", "nombre_municipio"])
        if not frame.empty:
            frame = (
                frame.drop_duplicates("cod_municipio")
                .sort_values("cod_municipio")
                .reset_index(drop=True)
            )
        return frame

    def _fetch_municipios(self, region_id: str) -> list[dict[str, str]]:
        """Return tidy municipio rows for one region (disk cache, then POST)."""
        cached = self._cached_municipios(region_id)
        if cached is not None:
            return cached
        rows = self._request_municipios(region_id)
        self._write_municipios_cache(region_id, rows)
        return rows

    def _municipios_cache_path(self, region_id: str) -> Path | None:
        """Disk-cache path for one region, or ``None`` when caching is off."""
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"municipios_{region_id}.json"

    def _cached_municipios(self, region_id: str) -> list[dict[str, str]] | None:
        """Load a region's cached rows; ``None`` if absent or unreadable."""
        path = self._municipios_cache_path(region_id)
        if path is None or not path.is_file():
            return None
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return rows if isinstance(rows, list) else None

    def _write_municipios_cache(self, region_id: str, rows: list[dict[str, str]]) -> None:
        """Persist a region's rows to the disk cache (no-op when off)."""
        path = self._municipios_cache_path(region_id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

    def _request_municipios(self, region_id: str) -> list[dict[str, str]]:
        """POST ``obtener_municipios.php`` for one region; return tidy rows."""
        response = self._http.post(
            _MUNICIPIOS_URL,
            headers=browser_headers(),
            data={
                "region": region_id,
                "municipio": "",
                "limit": "1000",
                "campo": "id_legal",
                "orden": "ASC",
                "pagina": "1",
            },
        )
        payload = json.loads(response.content.decode("utf-8"))
        return [
            {
                "cod_municipio": str(row.get("idLegal", "")).zfill(5),
                "nombre_municipio": row.get("municipio", ""),
            }
            for row in payload.get("textos", [])
        ]

    # -- data --------------------------------------------------------------

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
            Municipality (legal INE) codes to keep. Applied server-side and
            re-checked client-side. Defaults to all.
        regiones:
            Region ids to filter by (sent to the endpoint). Defaults to all.
        corrmon:
            Overrides the client's default monetary correction flag for
            this call only.
        tidy:
            If ``True`` (default), return long/tidy format with one row per
            (municipio, year, variable). If ``False``, pivot to wide with
            one column per variable code (``name``/``unit`` are dropped by
            the pivot).

        Returns
        -------
        pandas.DataFrame
            Tidy columns: ``cod_municipio``, ``nombre_municipio``, ``anio``,
            ``code``, ``name``, ``value``, ``unit``. ``name``/``unit`` are
            looked up from the catalog (:meth:`catalog`); an unknown code
            gets ``""`` for both rather than raising.
        """
        code_list = [str(codes)] if isinstance(codes, (str, int)) else [str(c) for c in codes]
        year_list = sorted(years) if years is not None else self.years()
        periods = ",".join(str(self._period_index(y)) for y in year_list)
        use_corrmon = self.corrmon if corrmon is None else corrmon

        muni_filter = {str(m).zfill(5) for m in municipios} if municipios else None
        variables_by_code = {variable.code: variable for variable in self._variables()}

        frames: list[pd.DataFrame] = []
        for code in code_list:
            params: list[tuple[str, str]] = [
                ("area[]", "T"),
                ("subarea[]", "T"),
                ("variables[]", code),
                ("periodos[]", periods),
                ("corrmon", "1" if use_corrmon else "0"),
            ]
            if regiones:
                params += [("regiones[]", str(r)) for r in regiones]
            else:
                params.append(("regiones[]", "T"))
            if municipios:
                params += [("municipios[]", str(m)) for m in municipios]
            else:
                params.append(("municipios[]", "T"))

            response = self._http.get(_DATA_URL, headers=data_headers(), params=params)
            records = parse_spreadsheet_xml(response.content)
            frame = pd.DataFrame(
                records,
                columns=["cod_municipio", "nombre_municipio", "anio", "value"],
            )
            variable = variables_by_code.get(code)
            frame.insert(3, "code", code)
            frame.insert(4, "name", variable.name if variable else "")
            frame["unit"] = variable.unit if variable else ""
            frames.append(frame)

        if frames:
            data = pd.concat(frames, ignore_index=True)
        else:
            data = pd.DataFrame(
                columns=[
                    "cod_municipio",
                    "nombre_municipio",
                    "anio",
                    "code",
                    "name",
                    "value",
                    "unit",
                ]
            )

        if muni_filter is not None and not data.empty:
            data = data[data["cod_municipio"].isin(muni_filter)].reset_index(drop=True)

        if tidy:
            return data
        return self._to_wide(data)

    @staticmethod
    def _to_wide(data: pd.DataFrame) -> pd.DataFrame:
        """Pivot tidy long data to wide (one column per variable code)."""
        if data.empty:
            return data
        wide = data.pivot_table(
            index=["cod_municipio", "nombre_municipio", "anio"],
            columns="code",
            values="value",
            aggfunc="first",
        )
        wide.columns.name = None
        return wide.reset_index()
