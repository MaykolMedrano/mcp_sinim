"""Parse SINIM SpreadsheetML responses into tidy records.

The ``obtener_datos_municipales.php`` endpoint returns an Excel 2003 XML
(SpreadsheetML) document. Layout verified against recorded responses:

* Row 0-1: title/note rows (styled cells).
* Row 2: the header row - ``CODIGO``, ``MUNICIPIO`` and one column per year
  (years in descending order, styled cells).
* Row 3+: one data row per municipality, with style-less ``<Cell>``
  elements holding the code, name and per-year values.

This module parses that format with :mod:`xml.etree.ElementTree`, never regex,
resolving ``ss:Index`` gaps, tolerating empty/short rows, and normalizing text
to UTF-8.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from typing import Any

#: SpreadsheetML namespace shared by every ``ss:``-prefixed name.
_SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
_ROW = f"{{{_SS_NS}}}Row"
_CELL = f"{{{_SS_NS}}}Cell"
_DATA = f"{{{_SS_NS}}}Data"
_INDEX_ATTR = f"{{{_SS_NS}}}Index"
_STYLE_ATTR = f"{{{_SS_NS}}}StyleID"

#: Matches a 4-digit year used as a data column header (e.g. ``"2024"``).
_YEAR_RE = re.compile(r"^\s*(\d{4})\s*$")
#: Matches and strips a leading XML prolog so :func:`ET.fromstring` receives a
#: Unicode string without a conflicting ``encoding=`` declaration.
_PROLOG_RE = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
#: Extracts ``encoding=`` from an XML prolog while the payload is still bytes.
_DECLARED_ENCODING_RE = re.compile(
    rb'^\s*<\?xml[^>]*encoding=["\']([A-Za-z][A-Za-z0-9._-]*)["\']',
    re.IGNORECASE,
)


class SpreadsheetXMLParseError(ValueError):
    """Raised when SINIM returns bytes that are not valid SpreadsheetML XML."""


def _declared_encoding(xml_bytes: bytes) -> str | None:
    """Return the XML prolog encoding, if one is declared."""
    match = _DECLARED_ENCODING_RE.match(xml_bytes)
    if match is None:
        return None
    return match.group(1).decode("ascii")


def _decode(xml_bytes: bytes) -> str:
    """Decode raw SINIM bytes, honoring the XML prolog before heuristics."""
    body = xml_bytes
    if body[:3] == b"\xef\xbb\xbf":
        body = body[3:]
    body = body.lstrip()

    declared = _declared_encoding(body)
    encodings = [declared] if declared is not None else []
    encodings.extend(
        encoding
        for encoding in ("utf-8", "latin-1")
        if encoding.lower() != (declared or "").lower()
    )

    last_exc: Exception | None = None
    for encoding in encodings:
        try:
            text = body.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            last_exc = exc
            continue
        return _PROLOG_RE.sub("", text, count=1).lstrip()

    raise SpreadsheetXMLParseError(
        "Could not decode the SINIM SpreadsheetML response using the declared "
        "encoding or the UTF-8/latin-1 fallbacks."
    ) from last_exc


def _to_float(raw: str) -> float:
    """Convert a SINIM cell string to float, tolerating locale decimals.

    Empty/blank cells and unparseable values become ``float(\"nan\")``. Chilean
    number formats (``1.234,5`` thousands+comma, or ``1234,5`` comma decimal)
    are normalized before parsing.
    """
    text = raw.strip()
    if not text:
        return math.nan
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return math.nan


def _cell_text(cell: ET.Element) -> str:
    """Return the stripped text of a cell's ``<Data>`` child, or ``""``."""
    data = cell.find(_DATA)
    if data is None or data.text is None:
        return ""
    return data.text.strip()


def _row_cells(row: ET.Element) -> dict[int, tuple[str, bool]]:
    """Map 1-based column index -> ``(text, has_style)`` honoring ``ss:Index``.

    SpreadsheetML cells default to consecutive columns; a ``ss:Index`` on a
    cell jumps the cursor to that 1-based column, leaving skipped columns
    empty.
    """
    cells: dict[int, tuple[str, bool]] = {}
    col = 0
    for cell in row.findall(_CELL):
        index = cell.get(_INDEX_ATTR)
        col = int(index) if index is not None else col + 1
        cells[col] = (_cell_text(cell), cell.get(_STYLE_ATTR) is not None)
    return cells


def parse_spreadsheet_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse a SINIM SpreadsheetML response into tidy long records.

    Parameters
    ----------
    xml_bytes:
        Raw response body from ``obtener_datos_municipales.php``, in its
        original encoding.

    Returns
    -------
    list[dict[str, typing.Any]]
        One dict per ``(municipality, year)`` with keys ``cod_municipio``
        (5-char, zero-padded), ``nombre_municipio``, ``anio`` (int) and
        ``value`` (float; ``NaN`` for missing/blank cells). Returns ``[]``
        when the document is valid XML but has no recognizable header/data
        rows.

    Raises
    ------
    SpreadsheetXMLParseError
        If ``xml_bytes`` is not well-formed SpreadsheetML XML.

    Notes
    -----
    Handles empty cells, ``ss:Index`` gaps, accented characters and short or
    ragged rows. The header row is located by content (the ``CODIGO`` marker),
    not a blind index, and years are read from the header labels so column
    order is irrelevant.
    """
    text = _decode(xml_bytes)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SpreadsheetXMLParseError(
            "SINIM returned bytes that are not valid SpreadsheetML XML."
        ) from exc

    rows = root.iter(_ROW)
    parsed = [_row_cells(row) for row in rows]

    header_idx: int | None = None
    year_cols: dict[int, int] = {}
    for idx, cells in enumerate(parsed):
        texts = {column: value for column, (value, _has_style) in cells.items()}
        if any(value.upper() == "CODIGO" for value in texts.values()):
            header_idx = idx
            for col, label in texts.items():
                match = _YEAR_RE.match(label)
                if match:
                    year_cols[col] = int(match.group(1))
            break

    if header_idx is None or not year_cols:
        return []

    records: list[dict[str, Any]] = []
    for cells in parsed[header_idx + 1 :]:
        code = cells.get(1, ("", False))[0]
        if not code or code.upper() == "CODIGO":
            continue
        if all(has_style for _value, has_style in cells.values()):
            continue
        cod_municipio = code.zfill(5)
        nombre = cells.get(2, ("", False))[0]
        for col, year in year_cols.items():
            value_text = cells.get(col, ("", False))[0]
            records.append(
                {
                    "cod_municipio": cod_municipio,
                    "nombre_municipio": nombre,
                    "anio": year,
                    "value": _to_float(value_text),
                }
            )
    return records
