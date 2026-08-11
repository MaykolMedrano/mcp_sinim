<div align="center">

# mcp-sinim

**Descarga datos municipales de Chile desde SINIM mediante un catálogo buscable, paneles ordenados y una misma herramienta para Python o cualquier cliente MCP.**

[![PyPI](https://img.shields.io/pypi/v/mcp-sinim.svg?style=flat-square&color=blue)](https://pypi.org/project/mcp-sinim/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/github/actions/workflow/status/MaykolMedrano/mcp_sinim/ci.yml?branch=main&style=flat-square&label=tests)](https://github.com/MaykolMedrano/mcp_sinim/actions/workflows/ci.yml)
[![Descargas](https://img.shields.io/pypi/dm/mcp-sinim?style=flat-square&color=blue&label=descargas)](https://pypi.org/project/mcp-sinim/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

</div>

---

## Descripción general

`mcp-sinim` ofrece dos interfaces para consultar el Sistema Nacional de
Información Municipal (SINIM) de Chile:

- un cliente síncrono de Python para análisis en notebooks y scripts;
- un servidor MCP para agentes de IA y otras aplicaciones compatibles.

Ambas interfaces utilizan el mismo catálogo de variables y entregan datos
municipales ordenados, listos para trabajar con `pandas`.

## Funcionalidades

- Buscar cerca de 480 variables por texto, sin memorizar códigos `id_dato`.
- Descargar uno o varios indicadores como paneles municipales ordenados.
- Consultar los años y códigos de municipios disponibles en el portal.
- Usar el paquete desde Python, notebooks o clientes MCP.
- Buscar en una copia local del catálogo y almacenar metadatos en caché.

## Instalación

```bash
pip install mcp-sinim
```

Requiere Python 3.10 o una versión posterior.

## Inicio rápido con Python

```python
from mcp_sinim import SINIMClient

client = SINIMClient(corrmon=True)

# 1) Buscar el código de una variable
resultados = client.search("patentes municipales")
print(resultados[["code", "name"]].head(3).to_string(index=False))

# 2) Descargar un panel para varios años y municipios
datos = client.get(
    ["4173", "1311"],
    years=[2022, 2023, 2024],
    municipios=["13101", "13114", "13123"],  # Santiago, Las Condes, Providencia
)
print(datos.head().to_string(index=False))

# 3) Explorar años y municipios
print(client.years()[-5:])
print(client.search_municipios("providencia"))
print(client.municipios(region="13"))  # código oficial de la Región Metropolitana

client.close()
```

Las columnas principales del resultado son:

| Columna | Contenido |
| :--- | :--- |
| `cod_municipio` | Código CUT oficial del municipio. |
| `nombre_municipio` | Nombre del municipio. |
| `year` | Año de la observación. |
| `code` | Código de la variable SINIM. |
| `name` | Nombre de la variable. |
| `value` | Valor publicado por SINIM. |
| `unit` | Unidad de medida. |

Métodos principales:

- `search(...)`: busca códigos de variables;
- `get(...)`: descarga datos municipales;
- `municipios(...)` y `search_municipios(...)`: consulta códigos CUT;
- `years()`: muestra los años disponibles.

Consulta también el [notebook de inicio rápido con mapa interactivo en
Kepler.gl](examples/basic_usage.ipynb) (Python 3.10–3.12), el [ejemplo básico en
Python](examples/basic_usage.py) y la [guía de usuario en
Jupyter](examples/Guia_Usuario_SINIM.ipynb).

## Servidor MCP para agentes de IA

Después de instalar el paquete, inicia el servidor con:

```bash
mcp-sinim
```

Configuración MCP habitual:

```json
{
  "mcpServers": {
    "sinim": {
      "command": "mcp-sinim"
    }
  }
}
```

Si el cliente MCP no encuentra el comando, usa la ruta completa del ejecutable
`mcp-sinim` correspondiente a tu entorno de Python.

Variable de entorno opcional:

- `MCP_SINIM_CACHE_DIR`: directorio para la caché de metadatos.

### Herramientas MCP

| Herramienta | Descripción |
| :--- | :--- |
| `search_variables` | Busca variables SINIM por palabras clave. |
| `get_variable_info` | Entrega los metadatos de una variable. |
| `get_data` | Descarga registros para una o varias variables. |
| `preview_data` | Previsualiza hasta 100 registros antes de exportar. |
| `export_data` | Exporta un panel completo a Parquet o CSV. |
| `list_areas` | Lista las nueve áreas temáticas del catálogo. |
| `list_municipios` | Lista municipios y permite filtrar por región. |
| `search_municipalities` | Busca municipios por nombre y región. |
| `list_years` | Lista los años disponibles actualmente. |

Ejemplos de solicitudes para un agente conectado al servidor:

> Busca variables relacionadas con ingresos propios municipales.

> Descarga la variable 4173 para Santiago, Las Condes y Providencia entre 2020 y 2024.

> Exporta a Parquet los ingresos por patentes de todos los municipios de la Región Metropolitana.

## Consideraciones sobre los datos

- `cod_municipio` corresponde a los códigos CUT oficiales de SUBDERE para los
  345 municipios presentes en SINIM.
- El argumento `municipios=` recibe esos códigos CUT y los traduce internamente
  a los identificadores utilizados por el portal.
- Los filtros regionales aceptan los códigos oficiales de Chile (`"1"` a
  `"16"`) y, por compatibilidad, los identificadores internos de SINIM.
- `corrmon=True` solicita la serie en valores reales, expresada en pesos del
  último año publicado.
- La unidad depende de cada variable. Por ejemplo, `M$` significa miles de pesos.
- La disponibilidad y cobertura histórica varían entre indicadores.

## Estructura del repositorio

```text
mcp_sinim/
├── mcp_sinim/          Cliente, catálogo, parsers y servidor MCP
│   └── data/            Copia local del catálogo de variables
├── examples/           Ejemplos, mapa Kepler.gl y guía en Jupyter
├── tests/              Pruebas automatizadas y datos de prueba
├── scripts/            Utilidades de catálogo, publicación y verificación
├── pyproject.toml      Configuración del paquete
└── README.md           Documentación principal
```

## Desarrollo

```bash
git clone https://github.com/MaykolMedrano/mcp_sinim
cd mcp_sinim
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

En macOS o Linux, activa el entorno con `source .venv/bin/activate`.

## Autor

**Maykol Medrano**<br>
Pontificia Universidad Católica de Chile<br>
Correo: [mmedrano2@uc.cl](mailto:mmedrano2@uc.cl)<br>
GitHub: [MaykolMedrano](https://github.com/MaykolMedrano)

## Licencia y descargo de responsabilidad

Este proyecto se distribuye bajo la [licencia MIT](LICENSE). Es un cliente
independiente de código abierto y no está afiliado a SUBDERE ni al Gobierno de
Chile. La disponibilidad y exactitud de los datos dependen del servicio público
de SINIM.
