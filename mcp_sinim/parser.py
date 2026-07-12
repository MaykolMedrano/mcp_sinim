"""Parse SINIM's XML SpreadsheetML data responses into tidy records.

The ``obtener_datos_municipales.php`` endpoint returns an XML Excel 2003
(SpreadsheetML) document. Layout (verified against real responses):

* Row 0-1: title/note rows (styled cells).
* Row 2: the header row — ``CODIGO``, ``MUNICIPIO`` and one column per year
  (years in **descending** order, styled cells).
* Row 3+: one data row per municipality, with **style-less** ``<Cell >``
  elements holding the code, name and per-year values.

This module parses that format with a real XML parser
(``xml.etree.ElementTree``) — never regex — resolving ``ss:Index`` gaps,
tolerating empty/short rows, and normalizing text to UTF-8. Despite what
older notes claim, the endpoint serves UTF-8 (no encoding declaration, so
XML defaults apply); we still fall back to latin-1 defensively.
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
#: Matches (and strips) a leading XML prolog, so a str with a declared
#: ``encoding=`` never trips ``ElementTree.fromstring``.
_PROLOG_RE = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)


def _decode(xml_bytes: bytes) -> str:
    """Decode raw SINIM bytes to text, UTF-8 first with a latin-1 fallback."""
    body = xml_bytes
    if body[:3] == b"\xef\xbb\xbf":  # strip UTF-8 BOM if present
        body = body[3:]
    body = body.lstrip()  # SINIM prepends a stray newline before <?xml
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    # Drop the prolog: fromstring() rejects a str that declares an encoding.
    return _PROLOG_RE.sub("", text, count=1).lstrip()


def _to_float(raw: str) -> float:
    """Convert a SINIM cell string to float, tolerating locale decimals.

    Empty/blank cells and unparseable values become ``float("nan")``. Chilean
    number formats (``1.234,5`` thousands+comma, or ``1234,5`` comma decimal)
    are normalized before parsing.
    """
    text = raw.strip()
    if not text:
        return math.nan
    if "," in text and "." in text:  # 1.234.567,89 -> 1234567.89
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:  # 1234,5 -> 1234.5
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return math.nan


def _cell_text(cell: ET.Element) -> str:
    """Return the (stripped) text of a cell's ``<Data>`` child, or ``""``."""
    data = cell.find(_DATA)
    if data is None or data.text is None:
        return ""
    return data.text.strip()


def _row_cells(row: ET.Element) -> dict[int, tuple[str, bool]]:
    """Map 1-based column index -> (text, has_style) honoring ``ss:Index``.

    SpreadsheetML cells default to consecutive columns; a ``ss:Index`` on a
    cell jumps the cursor to that (1-based) column, leaving the skipped
    columns empty.
    """
    cells: dict[int, tuple[str, bool]] = {}
    col = 0
    for cell in row.findall(_CELL):
        index = cell.get(_INDEX_ATTR)
        col = int(index) if index is not None else col + 1
        cells[col] = (_cell_text(cell), cell.get(_STYLE_ATTR) is not None)
    return cells


def parse_spreadsheet_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse a SINIM SpreadsheetML (XML) response into tidy long records.

    Parameters
    ----------
    xml_bytes:
        Raw response body from ``obtener_datos_municipales.php``, in its
        original encoding (UTF-8 in practice; latin-1 tolerated).

    Returns
    -------
    list[dict[str, typing.Any]]
        One dict per (municipality, year) with keys ``cod_municipio``
        (5-char, zero-padded), ``nombre_municipio``, ``anio`` (int) and
        ``value`` (float; ``NaN`` for missing/blank cells). Text is
        normalized to UTF-8 — callers never see mojibake. Returns ``[]``
        when the document has no recognizable header/data rows.

    Notes
    -----
    Handles empty cells, ``ss:Index`` gaps, accented (latin-1/UTF-8)
    characters and short/ragged rows. The header row is located by content
    (the ``CODIGO`` marker), not a blind index, and years are read from the
    header labels so column order is irrelevant.
    """
    text = _decode(xml_bytes)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    rows = root.iter(_ROW)
    parsed = [(_row_cells(row)) for row in rows]

    # Locate the header row by its "CODIGO" marker rather than a fixed index.
    header_idx: int | None = None
    year_cols: dict[int, int] = {}
    for idx, cells in enumerate(parsed):
        texts = {c: t for c, (t, _) in cells.items()}
        if any(t.upper() == "CODIGO" for t in texts.values()):
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
        # Data rows carry style-less cells; skip stray fully-styled rows.
        if all(has_style for _, has_style in cells.values()):
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
