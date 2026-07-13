"""Regenerate the packaged variable catalog from the live SINIM API.

Run from the repository root::

    python scripts/refresh_catalog.py

Used by the monthly ``refresh-catalog`` GitHub Actions workflow to keep
``mcp_sinim/data/catalog.json`` in sync with the SINIM portal.
"""

from __future__ import annotations

from mcp_sinim.catalog import DEFAULT_CATALOG_PATH, build_catalog, save_catalog
from mcp_sinim.client import SINIMClient


def main() -> None:
    with SINIMClient() as client:
        variables = build_catalog(client._fetch_catalog_raw())
    if not variables:
        raise SystemExit("SINIM returned an empty catalog; refusing to overwrite the snapshot.")
    save_catalog(variables, DEFAULT_CATALOG_PATH)
    print(f"Wrote {len(variables)} variables to {DEFAULT_CATALOG_PATH}")


if __name__ == "__main__":
    main()
