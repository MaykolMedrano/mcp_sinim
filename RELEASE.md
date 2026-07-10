# Release process

Versioning is dynamic via `setuptools-scm`, derived from git tags — there
is no version string to hand-edit anywhere in the repo.

## Steps

1. Ensure `main` is green in CI (ruff check, ruff format, pytest on the
   full 3.10–3.13 matrix).
2. Tag the release: `git tag v0.1.0 && git push origin v0.1.0`.
3. Enable the `publish` job in `.github/workflows/publish.yml` (remove the
   `if: false` guard) once PyPI trusted publishing is configured for this
   repo/environment.
4. Pushing the tag triggers `.github/workflows/publish.yml`, which builds
   the sdist/wheel and publishes to PyPI via trusted publishing (no API
   tokens stored in the repo).

## Pre-1.0

The public API (`SINIMClient`, MCP tools) may still change between minor
versions until `v1.0.0`.
