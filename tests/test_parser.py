"""Tests for :mod:`mcp_sinim.parser` against recorded and synthetic XML."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from mcp_sinim.parser import SpreadsheetXMLParseError, parse_spreadsheet_xml

FIXTURES = Path(__file__).parent / "fixtures"
_SPREADSHEET_NS = "urn:schemas-microsoft-com:office:spreadsheet"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _latin1_declared_workbook() -> bytes:
    """Return a SpreadsheetML payload that declares and uses latin-1."""
    xml = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        f'<Workbook xmlns="{_SPREADSHEET_NS}">'
        "<Worksheet><Table>"
        "<Row><Cell><Data>CODIGO</Data></Cell><Cell><Data>MUNICIPIO</Data></Cell>"
        "<Cell><Data>2024</Data></Cell></Row>"
        "<Row><Cell><Data>13120</Data></Cell><Cell><Data>\xd1U\xd1OA</Data></Cell>"
        "<Cell><Data>123</Data></Cell></Row>"
        "</Table></Worksheet></Workbook>"
    )
    return xml.encode("latin-1")


class TestRealResponse:
    """Variable 4173 (patentes), years 2022-2024, all municipalities."""

    def setup_method(self) -> None:
        self.records = parse_spreadsheet_xml(_load("data_4173_2022_2024.xml"))

    def test_shape_is_345_municipios_by_3_years(self) -> None:
        assert len(self.records) == 1035
        assert {r["anio"] for r in self.records} == {2022, 2023, 2024}
        assert len({r["cod_municipio"] for r in self.records}) == 345

    def test_known_values(self) -> None:
        by_key = {(r["cod_municipio"], r["anio"]): r["value"] for r in self.records}
        assert by_key[("13101", 2024)] == 24768668.0
        assert by_key[("01101", 2022)] == 11511926.0

    def test_codes_are_zero_padded_five_chars(self) -> None:
        assert all(len(r["cod_municipio"]) == 5 for r in self.records)
        assert any(r["cod_municipio"].startswith("0") for r in self.records)

    def test_missing_cells_become_nan(self) -> None:
        non_nan = sum(1 for r in self.records if not math.isnan(r["value"]))
        assert non_nan == 1031

    def test_names_have_no_mojibake(self) -> None:
        names = {r["nombre_municipio"] for r in self.records}
        assert not any("\u00c3" in n or "\u00c2" in n for n in names)
        assert any("\u00d1" in n or "\u00f1" in n for n in names)


class TestEdgeCases:
    def test_edge_case_fixture_parses(self) -> None:
        records = parse_spreadsheet_xml(_load("data_edge_cases.xml"))
        assert isinstance(records, list)
        for record in records:
            assert set(record) == {"cod_municipio", "nombre_municipio", "anio", "value"}
            assert len(record["cod_municipio"]) == 5
            assert isinstance(record["anio"], int)

    def test_garbage_input_raises_parse_error(self) -> None:
        with pytest.raises(SpreadsheetXMLParseError):
            parse_spreadsheet_xml(b"not xml at all")
        with pytest.raises(SpreadsheetXMLParseError):
            parse_spreadsheet_xml(b"")

    def test_xml_without_header_returns_empty(self) -> None:
        xml = (
            b'<?xml version="1.0"?>'
            b'<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet">'
            b"<Worksheet><Table><Row><Cell><Data>hola</Data></Cell></Row>"
            b"</Table></Worksheet></Workbook>"
        )
        assert parse_spreadsheet_xml(xml) == []

    def test_declared_encoding_is_respected_before_fallbacks(self) -> None:
        records = parse_spreadsheet_xml(_latin1_declared_workbook())
        assert records == [
            {
                "cod_municipio": "13120",
                "nombre_municipio": "\u00d1U\u00d1OA",
                "anio": 2024,
                "value": 123.0,
            }
        ]
