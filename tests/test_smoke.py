"""Smoke tests for the Phase 0 scaffold.

These only check that the package imports cleanly and that the public API
signatures from SPEC.md ("Contratos de la librería") exist — they must
pass against the unimplemented skeletons. Behavioral tests land alongside
each module's implementation in later phases.
"""

from __future__ import annotations

import inspect

import pytest

import mcp_sinim
from mcp_sinim import SINIMClient
from mcp_sinim.catalog import build_catalog, load_catalog, save_catalog
from mcp_sinim.parser import parse_spreadsheet_xml
from mcp_sinim.search_engine import search_municipios, search_variables
from mcp_sinim.server import (
    get_data,
    get_variable_info,
    list_areas,
    list_municipios,
    main,
)
from mcp_sinim.server import search_variables as server_search_variables


def test_package_exports_client_and_version() -> None:
    assert mcp_sinim.SINIMClient is SINIMClient
    assert isinstance(mcp_sinim.__version__, str)
    assert mcp_sinim.__version__


def test_client_constructor_signature_and_defaults() -> None:
    sig = inspect.signature(SINIMClient.__init__)
    assert list(sig.parameters) == ["self", "corrmon", "cache_dir", "timeout"]

    client = SINIMClient()
    assert client.corrmon is False
    assert client.cache_dir is None
    assert client.timeout == 30


@pytest.mark.parametrize(
    "method_name",
    ["catalog", "search", "get", "municipios", "years"],
)
def test_client_public_methods_exist(method_name: str) -> None:
    assert hasattr(SINIMClient, method_name)
    assert callable(getattr(SINIMClient, method_name))


@pytest.mark.parametrize(
    "func",
    [
        build_catalog,
        load_catalog,
        save_catalog,
        parse_spreadsheet_xml,
        search_variables,
        search_municipios,
    ],
)
def test_module_level_functions_are_callable(func) -> None:
    assert callable(func)
    assert func.__doc__


@pytest.mark.parametrize(
    "tool",
    [server_search_variables, get_variable_info, get_data, list_areas, list_municipios],
)
def test_server_tools_are_registered_and_callable(tool) -> None:
    assert callable(tool)


def test_server_main_entry_point_exists() -> None:
    assert callable(main)
    assert inspect.signature(main).parameters == {}
