"""The MCP server: wires the analysis modules up as tools an agent can call."""

from __future__ import annotations

import functools
import inspect
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from abap_mcp import __version__, rules, tooling
from abap_mcp.outline import outline
from abap_mcp.workspace import Workspace, WorkspaceError

INSTRUCTIONS = """\
Tools for reading, reviewing and testing ABAP code stored as abapGit files.
No SAP system is needed. Typical flow when changing an object:
1. list_objects to see what exists, outline_object to understand a class.
2. Edit the .abap files.
3. check_conventions for a fast Clean ABAP review, lint for full static analysis.
4. run_tests when the project runs ABAP Unit on Node.js.
Paths are relative to the workspace root the server was started with."""

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)


def create_server(root: Path | str | None = None) -> MCPServer:
    """Build a server bound to one workspace folder."""
    workspace = Workspace(root or os.environ.get("ABAP_MCP_ROOT") or Path.cwd())
    server = MCPServer(name="abap-mcp", version=__version__, instructions=INSTRUCTIONS)

    def guarded(func: Any) -> Any:
        """Turn workspace errors into a readable result instead of a stack trace."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                result: dict[str, Any] = func(*args, **kwargs)
                return result
            except WorkspaceError as error:
                return {"error": str(error)}

        wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]
        return wrapper

    @server.tool(annotations=READ_ONLY)
    @guarded
    def list_objects(path: str = ".") -> dict[str, Any]:
        """List the ABAP objects (classes, interfaces, programs...) in an abapGit folder.

        Args:
            path: Project folder relative to the workspace root.
        """
        objects = workspace.objects(path)
        return {"count": len(objects), "objects": [obj.to_dict() for obj in objects]}

    @server.tool(annotations=READ_ONLY)
    @guarded
    def outline_object(object_name: str, path: str = ".") -> dict[str, Any]:
        """Describe a class or interface: methods with visibility and signature,
        attributes, test classes, and the line range of every method body.

        Args:
            object_name: Object name, e.g. ZCL_ORDER_TOTAL.
            path: Project folder relative to the workspace root.
        """
        obj = workspace.find(object_name, path)
        files = []
        for file, text in workspace.read_source(obj).items():
            files.append({"file": file, "classes": [cls.to_dict() for cls in outline(text)]})
        return {"object": obj.name, "type": obj.type_label, "files": files}

    @server.tool(annotations=READ_ONLY)
    @guarded
    def check_conventions(
        source: str | None = None,
        object_name: str | None = None,
        path: str = ".",
        max_method_statements: int = 40,
    ) -> dict[str, Any]:
        """Review ABAP against Clean ABAP conventions. Fast and needs no Node.js.

        Pass either `source` (a snippet you just wrote) or `object_name` (an
        object in the workspace). Each finding cites the style guide section.

        Args:
            source: ABAP source text to review.
            object_name: Name of an object in the workspace to review instead.
            path: Project folder relative to the workspace root.
            max_method_statements: Statement limit for a single method.
        """
        if (source is None) == (object_name is None):
            return {"error": "Pass exactly one of 'source' or 'object_name'"}
        if source is not None:
            texts = {"<source>": source}
        else:
            assert object_name is not None
            texts = workspace.read_source(workspace.find(object_name, path))
        findings = [
            {"file": file, **finding.to_dict()}
            for file, text in texts.items()
            for finding in rules.check(text, max_method_statements=max_method_statements)
        ]
        return {"count": len(findings), "findings": findings, "guide": rules.GUIDE_URL}

    @server.tool(annotations=READ_ONLY)
    @guarded
    def lint(source: str | None = None, path: str = ".") -> dict[str, Any]:
        """Run abaplint static analysis (syntax, types, obsolete code, naming).

        Lints `source` when given, otherwise the project at `path`, using the
        project's own abaplint.json if it has one. Requires Node.js.

        Args:
            source: ABAP source text to lint instead of a project.
            path: Project folder relative to the workspace root.
        """
        if source is not None:
            return tooling.lint_source(source)
        return tooling.lint_project(workspace, path)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, idempotent_hint=True, open_world_hint=True))
    @guarded
    def run_tests(path: str, install: bool = False) -> dict[str, Any]:
        """Run the ABAP Unit tests of a project that executes them on Node.js
        (abaplint transpiler + open-abap), via `npm test`. No SAP system needed.

        Args:
            path: Project folder containing package.json.
            install: Reinstall npm dependencies before testing.
        """
        return tooling.run_tests(workspace, path, install)

    @server.resource("abap-mcp://rules", mime_type="application/json")
    def rule_catalog() -> dict[str, Any]:
        """Every convention rule check_conventions applies, with its style guide section."""
        return {"guide": rules.GUIDE_URL, "rules": [r.describe() for r in rules.RULES]}

    return server
