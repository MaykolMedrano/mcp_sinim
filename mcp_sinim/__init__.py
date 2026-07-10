"""mcp_sinim — Python client and MCP server for Chile's SINIM municipal data.

Public API (v0.1)::

    from mcp_sinim import SINIMClient

    client = SINIMClient()
    client.catalog()
    client.search("ingresos propios")
    client.get(["codigo"], years=[2020, 2021])
"""

from mcp_sinim.client import SINIMClient

try:
    from mcp_sinim._version import version as __version__
except ImportError:  # pragma: no cover - fallback when setuptools-scm hasn't run yet
    __version__ = "0.0.0.dev0"

__all__ = ["SINIMClient", "__version__"]
