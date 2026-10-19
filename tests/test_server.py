"""End-to-end tests through a real MCP client, as an agent would call the tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from abap_mcp.server import create_server
from tests.conftest import read, requires_node

pytestmark = pytest.mark.anyio


async def call(root: Path, tool: str, **arguments: Any) -> dict[str, Any]:
    async with Client(create_server(root)) as client:
        result = await client.call_tool(tool, arguments)
    assert not result.is_error, result
    payload: dict[str, Any] = json.loads(result.content[0].text)  # type: ignore[union-attr]
    return payload


async def test_exposes_tools_and_rule_catalog(workspace_root: Path) -> None:
    async with Client(create_server(workspace_root)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        catalog = await client.read_resource("abap-mcp://rules")
    assert set(tools) == {"list_objects", "outline_object", "check_conventions", "lint", "run_tests"}
    assert tools["outline_object"].annotations.read_only_hint  # type: ignore[union-attr]
    assert "ABAP Unit" in (tools["run_tests"].description or "")
    assert len(json.loads(catalog.contents[0].text)["rules"]) == 8  # type: ignore[union-attr]


async def test_list_and_outline(workspace_root: Path) -> None:
    listing = await call(workspace_root, "list_objects", path="shop")
    assert listing["count"] == 4
    outline = await call(workspace_root, "outline_object", object_name="ZCL_ORDER_TOTAL", path="shop")
    main, tests = outline["files"][0], outline["files"][1]
    assert [m["name"] for m in main["classes"][0]["methods"]][:3] == ["constructor", "net_total", "gross_total"]
    assert tests["file"].endswith(".testclasses.abap")


async def test_check_conventions_on_object_and_snippet(workspace_root: Path) -> None:
    legacy = await call(workspace_root, "check_conventions", object_name="ZCL_LEGACY_INVOICE", path="shop")
    assert legacy["count"] > 10 and legacy["guide"].startswith("https://github.com/SAP/styleguides")
    snippet = await call(workspace_root, "check_conventions", source="MOVE a TO b.")
    assert [f["rule"] for f in snippet["findings"]] == ["no-obsolete-statements"]


async def test_reports_errors_instead_of_crashing(workspace_root: Path) -> None:
    assert "outside" in (await call(workspace_root, "list_objects", path="../.."))["error"]
    assert "not found" in (await call(workspace_root, "outline_object", object_name="ZCL_NOPE", path="shop"))["error"]
    assert "exactly one" in (await call(workspace_root, "check_conventions"))["error"]
    assert "package.json" in (await call(workspace_root, "run_tests", path="shop"))["error"]


@requires_node
@pytest.mark.node
async def test_lint_project_with_abaplint(workspace_root: Path) -> None:
    result = await call(workspace_root, "lint", path="shop")
    assert result["available"] and result["config"] == "default"
    files = {issue["file"] for issue in result["issues"]}
    assert files == {"shop/src/zcl_legacy_invoice.clas.abap"}, "the clean class must pass abaplint"
    assert {"obsolete_statement", "no_prefixes", "prefer_is_not"} <= {i["rule"] for i in result["issues"]}


@requires_node
@pytest.mark.node
async def test_lint_snippet_with_abaplint(workspace_root: Path) -> None:
    clean = await call(workspace_root, "lint", source=read("shop/src/zif_tax_rate.intf.abap"))
    assert clean["available"] and clean["issues"] == []
