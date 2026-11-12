---
paths:
  - "tests/**"
  - "src/**/*.py"
---
# Testing

- pytest with anyio. Fixtures in `tests/fixtures/`.
- Tests needing Node.js and abaplint carry the `node` marker.
- Every tool gets: a happy path, invalid arguments rejected, a path outside the workspace rejected.
- Run `ruff check . && ruff format --check . && mypy src && pytest -q` before every commit.
