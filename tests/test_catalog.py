"""Offline tests for :mod:`mcp_sinim.catalog` (no network).

Two data sources are used:

* A small hand-built raw payload (below) that exercises the normalization
  edge cases: a trailing-space unit symbol, a null ``fuente_nombre``, and a
  variable code (``id_dato``) duplicated across two different subarea
  groups.
* The real recon snapshot (``recon/catalog_raw_2026-07-08.json``) to check
  the actual packaged catalog end to end.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mcp_sinim.catalog import (
    CATALOG_FIELDS,
    Variable,
    build_catalog,
    load_catalog,
    packaged_catalog,
    save_catalog,
)

RECON_RAW = Path(__file__).parent.parent / "recon" / "catalog_raw_2026-07-08.json"


def _sample_raw() -> dict:
    return {
        "SUBAREA UNO": [
            {
                "id_area": 1,
                "nombre_area": "01.  FINANZAS",
                "id_subarea": 10,
                "nombre_subarea": "SUBAREA UNO",
                "unidad_medida_simbolo": "M$  ",
                "unidad_medida_nombre": "MILES DE PESOS",
                "fuente_nombre": "BEP Municipal",
                "id_dato": 1001,
                "mtro_datos_nombre": "Ingresos Totales ",
            },
            {
                "id_area": 1,
                "nombre_area": "01.  FINANZAS",
                "id_subarea": 10,
                "nombre_subarea": "SUBAREA UNO",
                "unidad_medida_simbolo": "N°  ",
                "unidad_medida_nombre": "NUMERO ENTERO",
                "fuente_nombre": None,
                "id_dato": 1002,
                "mtro_datos_nombre": "Cantidad de Patentes",
            },
        ],
        "SUBAREA DOS": [
            # Same id_dato as 1001 above, in a *different* subarea group --
            # must be deduplicated, first occurrence (payload order) wins.
            {
                "id_area": 2,
                "nombre_area": "02.  OTRA AREA",
                "id_subarea": 20,
                "nombre_subarea": "SUBAREA DOS",
                "unidad_medida_simbolo": "M$",
                "unidad_medida_nombre": "MILES DE PESOS",
                "fuente_nombre": "Fuente Duplicada",
                "id_dato": 1001,
                "mtro_datos_nombre": "Ingresos Totales (duplicado)",
            },
        ],
    }


def test_variable_is_frozen() -> None:
    variable = Variable(
        code="1", name="a", area="b", subarea="c", unit="d", unit_name="e", source="f"
    )
    with pytest.raises(FrozenInstanceError):
        variable.code = "2"  # type: ignore[misc]


def test_build_catalog_normalizes_and_dedups_by_code() -> None:
    variables = build_catalog(_sample_raw())
    assert len(variables) == 2  # 1001 deduped (kept once), 1002 kept

    by_code = {v.code: v for v in variables}
    assert set(by_code) == {"1001", "1002"}

    # First occurrence wins for a code duplicated across subarea groups.
    first = by_code["1001"]
    assert first.name == "Ingresos Totales"  # trailing space stripped
    assert first.source == "BEP Municipal"
    assert first.subarea == "SUBAREA UNO"

    second = by_code["1002"]
    assert second.unit == "N°"  # unidad_medida_simbolo trailing spaces stripped
    assert second.unit_name == "NUMERO ENTERO"
    assert second.source == ""  # null fuente_nombre -> ""


def test_build_catalog_real_recon_snapshot_has_no_duplicate_codes() -> None:
    raw = json.loads(RECON_RAW.read_text(encoding="utf-8"))
    total_raw_entries = sum(len(entries) for entries in raw.values())
    variables = build_catalog(raw)

    # Documented in SPEC.md: 480 variables. The raw snapshot happens to
    # have zero id_dato collisions across subareas, so dedup is a no-op
    # here -- but build_catalog must still dedup correctly if it isn't.
    assert total_raw_entries == 480
    assert len(variables) == 480
    assert len({v.code for v in variables}) == len(variables)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    raw = json.loads(RECON_RAW.read_text(encoding="utf-8"))
    variables = build_catalog(raw)
    path = tmp_path / "catalog.json"

    save_catalog(variables, path)
    loaded = load_catalog(path)

    assert {v.code: v for v in loaded} == {v.code: v for v in variables}
    assert loaded == sorted(loaded, key=lambda v: int(v.code))  # persisted sorted by code

    text = path.read_text(encoding="utf-8")
    assert "\\u" not in text  # ensure_ascii=False: accents stay literal
    assert "\r\n" not in text  # stable across platforms

    payload = json.loads(text)
    assert list(payload[0].keys()) == CATALOG_FIELDS


def test_load_catalog_defaults_to_packaged_path() -> None:
    variables = load_catalog()  # default path == DEFAULT_CATALOG_PATH
    assert len(variables) == 480


def test_packaged_catalog_loads_480_unique_variables() -> None:
    variables = packaged_catalog()
    assert len(variables) == 480
    assert len({v.code for v in variables}) == 480

    codes = {v.code for v in variables}
    assert "4173" in codes  # Ingresos por Patentes Municipales de Beneficio Municipal

    areas = {v.area.strip() for v in variables}
    assert len(areas) == 9  # SPEC.md: 9 areas
