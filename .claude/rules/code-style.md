---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---
# Python code style

- Python 3.11+, `mypy --strict` clean, ruff rules from pyproject.toml (line length 120).
- `server.py` only registers tools and resources and maps arguments; logic lives in `outline.py`, `rules.py`, `source.py`, `workspace.py`.
- Every external process goes through `tooling.py`.
- Tool results are structured and size-bounded; error messages never leak absolute paths outside the workspace.
- Public tool names, parameters and descriptions are a contract: keep them stable and documented in README.md.
