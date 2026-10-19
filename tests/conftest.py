from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from abap_mcp.tooling import abaplint_command

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A throwaway copy of the fixture workspace, so tests can never modify it."""
    root = tmp_path / "workspace"
    shutil.copytree(FIXTURES, root)
    return root


def read(relative: str) -> str:
    return (FIXTURES / relative).read_text(encoding="utf-8")


requires_node = pytest.mark.skipif(
    abaplint_command() is None or shutil.which("node") is None,
    reason="Node.js with abaplint (or npx) is not available",
)
