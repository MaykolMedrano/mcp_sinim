"""Tests for :mod:`mcp_sinim.parser` against recorded SINIM responses.

The fixtures under ``tests/fixtures/`` are real API payloads captured on
2026-07 (see ``recon/``); the concrete values asserted here were verified
by hand against the recorded XML.
"""

from __future__ import annotations

import math
from pathlib import Path

from mcp_sinim.parser import parse_spreadsheet_xml

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


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
        assert by_key[("13101", 2024)] == 24768668.0  # SANTIAGO
        assert by_key[("01101", 2022)] == 11511926.0  # IQUIQUE

    def test_codes_are_zero_padded_five_chars(self) -> None:
        assert all(len(r["cod_municipio"]) == 5 for r in self.records)
        assert any(r["cod_municipio"].startswith("0") for r in self.records)

    def test_missing_cells_become_nan(self) -> None:
        non_nan = sum(1 for r in self.records if not math.isnan(r["value"]))
        assert non_nan == 1031  # 4 recorded blanks in this extract

    def test_names_have_no_mojibake(self) -> None:
        names = {r["nombre_municipio"] for r in self.records}
        assert not any("Ã" in n or "Â" in n for n in names)
        assert any("Ñ" in n or "ñ" in n for n in names)  # e.g. ÑUÑOA / PEÑALOLEN


class TestEdgeCases:
    def test_edge_case_fixture_parses(self) -> None:
        records = parse_spreadsheet_xml(_load("data_edge_cases.xml"))
        assert isinstance(records, list)
        for r in records:
            assert set(r) == {"cod_municipio", "nombre_municipio", "anio", "value"}
            assert len(r["cod_municipio"]) == 5
            assert isinstance(r["anio"], int)

    def test_garbage_input_returns_empty(self) -> None:
        assert parse_spreadsheet_xml(b"not xml at all") == []
        assert parse_spreadsheet_xml(b"") == []

    def test_xml_without_header_returns_empty(self) -> None:
        xml = (
            b'<?xml version="1.0"?>'
            b'<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet">'
            b"<Worksheet><Table><Row><Cell><Data>hola</Data></Cell></Row>"
            b"</Table></Worksheet></Workbook>"
        )
        assert parse_spreadsheet_xml(xml) == []
