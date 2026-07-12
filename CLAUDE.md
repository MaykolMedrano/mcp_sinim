# mcp_sinim — Especificación y estándares del proyecto

Librería Python + servidor MCP para el SINIM (Sistema Nacional de Información
Municipal de Chile, datos.sinim.gov.cl): ~345 comunas, 2000–2024, 480 variables
en 9 áreas (finanzas, RRHH, educación, salud, social, territorial, género...).
Cuarto miembro de la familia mcp_* de Maykol Medrano (mcp_bcrp, mcp_imf,
mcp_wbgapi360) — sigue sus mismas convenciones.

## Producto

- **v0.1**: paquete único `mcp-sinim` con dos puertas de entrada:
  - Librería: `from mcp_sinim import SINIMClient` (usable sin MCP)
  - Servidor MCP: `mcp-sinim` (entry point) sobre FastMCP
- **v0.2** (futuro, no implementar aún): comando Stata `sinim` (carpeta
  `stata/`) vía integración `python:` de Stata 16+.

## API del SINIM (reconocimiento verificado 2026-07-08)

Todo probado en vivo. Los archivos de `recon/` son la evidencia.

### 1. Catálogo de variables — POST
```
POST https://datos.sinim.gov.cl/datos_municipales/obtener_datos_filtros.php
body (form, estilo array PHP): dato_area[]=T&dato_subarea[]=T
headers OBLIGATORIOS (sin ellos responde "Error inesperado"):
  User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3.1 Safari/605.1.15
  Referer: https://datos.sinim.gov.cl/datos_municipales.php
  X-Requested-With: XMLHttpRequest
  Accept-Encoding: gzip, deflate, br
```
Respuesta: JSON `{nombre_subarea: [ {id_area, nombre_area, id_subarea,
nombre_subarea, unidad_medida_simbolo, unidad_medida_nombre, fuente_nombre,
id_dato, mtro_datos_nombre}, ... ]}`. `id_dato` es el código de variable.
Muestra completa en `recon/catalog_raw_2026-07-08.json` (480 variables).

### 2. Datos — GET (XML SpreadsheetML)
```
GET https://datos.sinim.gov.cl/datos_municipales/obtener_datos_municipales.php
  ?area[]=T&subarea[]=T&variables[]={id_dato}&periodos[]={idx,...}
  &regiones[]=T&municipios[]=T&corrmon={0|1}
header: X-Request-Source: r  (+ User-Agent de arriba)
```
- `periodos[]` usa índices 1-based sobre la lista de años disponibles
  (2000=1, 2001=2, ...). OJO: descubrir la lista de años dinámicamente
  (select del formulario o obtener_cabecera.php) con fallback a
  `range(2000, año_actual)`; no hardcodear el tope.
- `corrmon=1` aplica corrección monetaria (pesos reales).
- Respuesta: XML estilo Excel 2003. Parsing de referencia en
  `recon/aux_sinim_patentes_original.py` (regex sobre `<Row>`/`<Cell>`;
  cabecera = fila 3; datos = celdas sin StyleID). Reimplementar con
  parser XML de verdad (`xml.etree` o `lxml`), no regex.
- Encoding: ISO-8859-1 / latin-1 en varios endpoints. Normalizar a UTF-8
  en el borde y NUNCA dejar mojibake en outputs.

### 3. Municipios — POST
```
POST https://datos.sinim.gov.cl/datos_municipales/obtener_municipios.php
body: region={id}   (mismos headers del catálogo)
```
Los ids de región se descubren DINÁMICAMENTE del select del formulario
(implementado en `client._region_ids()`); no hardcodear — la lista estática
original de esta spec estaba desactualizada (ej.: Metropolitana es 131).
El body real del POST municipios lleva además: municipio, limit, campo
(id_legal), orden, pagina — ver `client._fetch_municipios()`.
Nota verificada 2026-07: el formulario publica años 2001–2025 (índice
1-based con base 2000), otra razón para el descubrimiento dinámico.

## Arquitectura

```
mcp_sinim/                  # paquete (import mcp_sinim)
├── __init__.py             # exporta SINIMClient, __version__
├── __main__.py             # python -m mcp_sinim → server
├── _version.py             # setuptools-scm
├── client.py               # SINIMClient (httpx): catálogo, datos, municipios
├── parser.py               # XML SpreadsheetML → registros tidy
├── catalog.py              # modelo del catálogo + build desde API + carga local
├── search_engine.py        # fuzzy search (rapidfuzz) variables/comunas
└── server.py               # FastMCP tools
data/catalog.json           # catálogo empaquetado (generado por catalog.py)
tests/                      # pytest, fixtures OFFLINE en tests/fixtures/
examples/                   # notebook Guía_Usuario_SINIM.ipynb + basic_usage.py
recon/                      # evidencia del reconocimiento (no se empaqueta)
```

## Contratos de la librería (API pública v0.1)

```python
client = SINIMClient(corrmon=False, cache_dir=None, timeout=30)
client.catalog() -> pd.DataFrame            # 480 vars: code, name, area, subarea, unit, source
client.search(query, limit=10) -> pd.DataFrame   # fuzzy sobre el catálogo
client.get(codes, years=None, municipios=None, regiones=None, corrmon=None,
           tidy=True) -> pd.DataFrame
# tidy long: cod_municipio, nombre_municipio, anio, variable(code), name, value, unit
client.municipios(region=None) -> pd.DataFrame
client.years() -> list[int]                 # años disponibles, dinámico
```

## Tools del servidor MCP (FastMCP, nombre "sinim")

- `search_variables(query, area?)` — fuzzy sobre catálogo
- `get_variable_info(code)` — metadata completa
- `get_data(codes, years?, municipios?, region?, corrmon?)` — tabla (JSON records o CSV)
- `list_areas()` / `list_municipios(region?)`
- Docstrings de tools EN INGLÉS (consistencia con mcp_bcrp), mensajes de
  error accionables.

## Estándares INNEGOCIABLES

1. **Tests offline**: fixtures grabadas en `tests/fixtures/` (XML de datos,
   JSON de catálogo). CI jamás toca datos.sinim.gov.cl. Cobertura de:
   parser (casos: celdas vacías, latin-1, filas cortas), client (con
   respx/mock), catalog, search, server tools.
2. **Ruff**: `ruff check` y `ruff format` limpios. Config en pyproject.
3. **Type hints completos** en todo el código público.
4. **Cortesía de red**: rate limit (≥0.5 s entre requests), retries con
   backoff exponencial (tenacity o manual), timeout explícito, User-Agent
   del proyecto: `mcp-sinim/{version} (+https://github.com/MaykolMedrano/mcp_sinim)`
   — EXCEPTO en los endpoints que exigen el UA de navegador (catálogo):
   ahí usar el UA de navegador documentado arriba.
5. **pyproject**: setuptools>=45 + setuptools-scm>=8, `dynamic = ["version"]`,
   MIT, requires-python >=3.10, authors Maykol Medrano <mmedrano2@uc.cl>,
   `[project.scripts] mcp-sinim = "mcp_sinim.server:main"`.
   Deps runtime: fastmcp, httpx, pandas, rapidfuzz. Dev: pytest,
   pytest-asyncio, respx, ruff.
6. **CI GitHub Actions** (`.github/workflows/ci.yml`): matrix 3.10–3.13,
   pasos: ruff check, ruff format --check, pytest. Workflow de publish a
   PyPI en tags `v*` (trusted publishing) en archivo aparte, deshabilitado
   hasta el release.
7. **Docs**: README.md con badges, quickstart de librería Y de MCP
   (config para claude_desktop_config.json y claude mcp add), tabla de
   tools, sección de áreas/variables. CONTRIBUTING.md y RELEASE.md breves
   (copiar espíritu de mcp_bcrp). LICENSE MIT.
8. **Commits**: convencionales (`feat:`, `fix:`, `docs:`, `test:`, `chore:`),
   en inglés, uno por unidad de trabajo.
9. **Nada de rutas absolutas ni credenciales** en el código.
10. **Español en comentarios internos permitido; API pública y docstrings
    de tools en inglés.**

## Qué NO hacer

- No usar `requests` (usar httpx, como la familia).
- No parsear XML con regex en el código final.
- No hardcodear el año tope ni la lista de municipios.
- No agregar dependencias pesadas (nada de selenium/playwright aquí).
- No implementar la parte Stata todavía.
