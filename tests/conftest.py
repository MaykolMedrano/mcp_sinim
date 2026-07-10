"""Shared pytest fixtures for mcp_sinim tests.

Per project standards, all tests run offline against recorded fixtures in
``tests/fixtures/`` — CI never touches datos.sinim.gov.cl.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the offline test fixtures directory."""
    return FIXTURES_DIR
