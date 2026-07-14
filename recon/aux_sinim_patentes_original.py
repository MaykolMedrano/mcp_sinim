"""
AUX_SINIM_PATENTES.PY
Descarga datos de patentes municipales desde SINIM (datos.sinim.gov.cl)
y guarda panel comunal 2000-2024 en parquet.

Variables descargadas:
  4173 = Ingresos por Patentes Municipales de Beneficio Municipal (M$ nominales)
  1311 = Monto Patentes Municipales Pagadas (M$ nominales)

OUTPUT: 01_data/02_intermediate/SINIM/sinim_patentes_2000_2024.parquet
"""

import os
import re, time, sys
import requests
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Keep recon output portable: callers can set SINIM_PROJECT_ROOT, otherwise
# the script writes relative to the current working directory.
ROOT = Path(os.environ.get("SINIM_PROJECT_ROOT", Path.cwd()))
OUT  = ROOT / "01_data/02_intermediate/SINIM/sinim_patentes_2000_2024.parquet"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── Mapeo año → índice SINIM (igual que getyear() en sinimr) ──────────────────
YEAR_LIST = list(range(2000, 2025))   # 2000–2024
def getyear(y): return YEAR_LIST.index(y) + 1  # 1-based

# Variables a descargar
VARIABLES = {
    4173: "pat_benef_munic",   # De Beneficio Municipal (comparable a CGR)
    1311: "pat_pagadas_total", # Monto total Pagadas
}

# ── Sesión HTTP ────────────────────────────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.3.1 Safari/605.1.15"
    ),
    "X-Request-Source": "r",
})
BASE = "https://datos.sinim.gov.cl/datos_municipales/obtener_datos_municipales.php"


def parse_xml_rows(text: str):
    """
    Parsea filas de datos del XML de SINIM.
    Las celdas de datos tienen <Cell > (sin StyleID).
    Las celdas de cabecera tienen <Cell ss:StyleID="...">.
    Devuelve (encabezados, lista_de_filas_data).
    """
    rows = re.findall(r"<Row\b[^>]*>(.*?)</Row>", text, re.DOTALL)

    # Fila 3 (índice 2) = cabecera de columnas
    header_row = rows[2] if len(rows) > 2 else ""
    headers = re.findall(r"<Data[^>]*>([^<]*)</Data>", header_row)

    # Filas de datos: celdas SIN StyleID (desde fila 4, índice 3)
    data_rows = []
    for row in rows[3:]:
        cells = re.findall(r"<Cell\s><Data[^>]*>([^<]*)</Data></Cell>", row)
        if cells:
            data_rows.append(cells)

    return headers, data_rows


def download_variable(var_code: int, years: list[int]) -> pd.DataFrame:
    """
    Descarga una variable para la lista de años dada.
    Devuelve DataFrame long: cod_municipio, nombre_municipio, anio, value
    """
    idx_str = ",".join(str(getyear(y)) for y in years)
    url = (
        f"{BASE}?area[]=T&subarea[]=T"
        f"&variables[]={var_code}"
        f"&periodos[]={idx_str}"
        f"&regiones[]=T&municipios[]=T&corrmon=0"
    )

    for attempt in range(3):
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(5)

    text = resp.text[1:]  # strip leading BOM char como en sinimr

    headers, data_rows = parse_xml_rows(text)
    print(f"  var={var_code}: {len(data_rows)} comunas, "
          f"{len(headers)} cols → {headers[:6]}...")

    if not data_rows:
        raise ValueError(f"No data rows for var {var_code}, years {years}")

    expected_cols = 2 + len(years)  # CODIGO + MUNICIPIO + N años
    records = []
    for row in data_rows:
        if len(row) < expected_cols:
            continue
        cod  = str(row[0]).zfill(5)
        muni = row[1]
        for i, yr in enumerate(sorted(years, reverse=True)):  # SINIM: desc
            val_str = row[2 + i]
            try:
                val = float(val_str)
            except (ValueError, IndexError):
                val = float("nan")
            records.append({
                "cod_municipio":    cod,
                "nombre_municipio": muni,
                "anio":             yr,
                "value":            val,
            })

    return pd.DataFrame(records)


# ── Descarga por décadas para no sobrecargar ──────────────────────────────────
all_frames = []

for var_code, var_name in VARIABLES.items():
    print(f"\nDescargando var {var_code} ({var_name})...")

    # Dividir en bloques de 5 años para reducir timeout
    years_all = list(range(2000, 2025))  # 2000–2024
    chunks = [years_all[i:i+5] for i in range(0, len(years_all), 5)]

    frames_var = []
    for chunk in chunks:
        print(f"  Años {chunk[0]}–{chunk[-1]}...")
        df_chunk = download_variable(var_code, chunk)
        frames_var.append(df_chunk)
        time.sleep(1)

    df_var = pd.concat(frames_var, ignore_index=True)
    df_var = df_var.rename(columns={"value": var_name})
    all_frames.append(df_var.set_index(["cod_municipio", "nombre_municipio", "anio"]))
    print(f"  Total: {len(df_var):,} obs para {var_code}")

# ── Combinar variables ─────────────────────────────────────────────────────────
panel = pd.concat(all_frames, axis=1).reset_index()
panel = panel.sort_values(["cod_municipio", "anio"]).reset_index(drop=True)

print(f"\nPanel final: {len(panel):,} obs, {panel['cod_municipio'].nunique()} comunas, "
      f"años {panel['anio'].min()}–{panel['anio'].max()}")
print(panel[panel["nombre_municipio"].str.contains("REINA", na=False)].to_string())

panel.to_parquet(OUT, index=False)
print(f"\n[ok] → {OUT}")
