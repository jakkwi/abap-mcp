from pathlib import Path

import pytest

from abap_mcp.workspace import Workspace, WorkspaceError


def test_lists_objects_with_types_and_files(workspace_root: Path) -> None:
    objects = {o.name: o for o in Workspace(workspace_root).objects("shop")}
    assert set(objects) == {"ZCL_ORDER_TOTAL", "ZCL_LEGACY_INVOICE", "ZIF_TAX_RATE", "PACKAGE"}
    order = objects["ZCL_ORDER_TOTAL"]
    assert order.type == "CLAS" and order.type_label == "class"
    assert order.files == [
        "shop/src/zcl_order_total.clas.abap",
        "shop/src/zcl_order_total.clas.testclasses.abap",
        "shop/src/zcl_order_total.clas.xml",
    ]


def test_find_is_case_insensitive_and_reads_only_abap(workspace_root: Path) -> None:
    workspace = Workspace(workspace_root)
    sources = workspace.read_source(workspace.find("zif_tax_rate", "shop"))
    assert list(sources) == ["shop/src/zif_tax_rate.intf.abap"]


def test_honours_starting_folder(workspace_root: Path) -> None:
    (workspace_root / "shop" / "src").rename(workspace_root / "shop" / "abap")
    config = workspace_root / "shop" / ".abapgit.xml"
    config.write_text(config.read_text().replace("/src/", "/abap/"))
    assert Workspace(workspace_root).find("ZCL_ORDER_TOTAL", "shop")


@pytest.mark.parametrize("path", ["..", "../..", "/etc", "shop/../../outside"])
def test_rejects_paths_outside_the_workspace(workspace_root: Path, path: str) -> None:
    with pytest.raises(WorkspaceError, match="outside the workspace"):
        Workspace(workspace_root).resolve(path)


def test_rejects_symlink_escaping_the_workspace(workspace_root: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.mkdir()
    (workspace_root / "link").symlink_to(secret)
    with pytest.raises(WorkspaceError, match="outside the workspace"):
        Workspace(workspace_root).resolve("link")


def test_unknown_object_raises(workspace_root: Path) -> None:
    with pytest.raises(WorkspaceError, match="not found"):
        Workspace(workspace_root).find("ZCL_NOPE", "shop")


def test_summarizes_abap_unit_output() -> None:
    from abap_mcp.tooling import summarize_test_output

    output = "PASS  LTCL_A -> WORKS\nFAIL  LTCL_A -> BREAKS\n\n1/2 tests passed\n"
    assert summarize_test_output(output) == {
        "failed_tests": ["LTCL_A -> BREAKS"],
        "tests_passed": 1,
        "tests_total": 2,
    }
