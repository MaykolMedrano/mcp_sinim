"""Parse SINIM's XML SpreadsheetML data responses into tidy records.

The ``obtener_datos_municipales.php`` endpoint returns an XML Excel 2003
(SpreadsheetML) document, latin-1/ISO-8859-1 encoded, with a header row at
index 3. This module parses that format with a real XML parser
(``xml.etree.ElementTree``) — never regex — and normalizes text to UTF-8.
"""

from __future__ import annotations

from typing import Any


def parse_spreadsheet_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse a SINIM SpreadsheetML (XML) response into tidy records.

    Parameters
    ----------
    xml_bytes:
        Raw response body from ``obtener_datos_municipales.php``, in its
        original encoding (typically ISO-8859-1/latin-1).

    Returns
    -------
    list[dict[str, typing.Any]]
        One dict per data row, with keys derived from the header row (row
        3 in the SINIM layout). Text is normalized to UTF-8; callers must
        never see mojibake.

    Notes
    -----
    Must handle: empty cells, latin-1 characters, and short/ragged rows.
    """
    raise NotImplementedError
