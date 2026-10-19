"""Run the Node.js ABAP toolchain: abaplint for static analysis, npm for tests.

Both are optional at runtime. The pure-Python tools keep working when Node.js
is missing; these return a clear "not available" result instead of crashing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from abap_mcp.workspace import Workspace

DEFAULT_LINT_CONFIG: dict[str, Any] = {
    "global": {"files": "/src/**/*.*"},
    "syntax": {"version": "v757", "errorNamespace": "^(Z|Y|LCL_|LTCL_|LTD_|LIF_)"},
    "rules": {
        "parser_error": True,
        "check_syntax": True,
        "unknown_types": True,
        "obsolete_statement": True,
        "unused_variables": True,
        "prefer_returning_to_exporting": True,
        "prefer_is_not": True,
        "no_prefixes": True,
        "empty_structure": True,
        "keyword_case": True,
        "line_length": {"length": 120},
        "method_length": {"statements": 40},
    },
}

_OBJECT_NAME = re.compile(r"^\s*(CLASS|INTERFACE)\s+([\w/]+)", re.IGNORECASE | re.MULTILINE)
TIMEOUT_SECONDS = int(os.environ.get("ABAP_MCP_TIMEOUT", "180"))


def abaplint_command() -> list[str] | None:
    """Find abaplint: an explicit override, a global install, or npx as a fallback."""
    override = os.environ.get("ABAP_MCP_ABAPLINT")
    if override:
        return override.split()
    if shutil.which("abaplint"):
        return ["abaplint"]
    if shutil.which("npx"):
        return ["npx", "--yes", "@abaplint/cli@2"]
    return None


def _snippet_filename(source: str) -> str:
    match = _OBJECT_NAME.search(source)
    if not match:
        return "zsnippet.prog.abap"
    kind = "clas" if match.group(1).upper() == "CLASS" else "intf"
    return f"{match.group(2).lower().replace('/', '#')}.{kind}.abap"


def _run_abaplint(folder: Path, config: Path) -> dict[str, Any]:
    command = abaplint_command()
    if command is None:
        return {"available": False, "error": "Node.js and abaplint are not installed", "issues": []}
    try:
        completed = subprocess.run(
            [*command, str(config), "--format", "json"],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"available": True, "error": f"abaplint timed out after {TIMEOUT_SECONDS}s", "issues": []}
    output = completed.stdout.strip()
    start = output.find("[")
    try:
        raw = json.loads(output[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return {"available": True, "error": (completed.stderr or output)[-2000:], "issues": []}
    issues = [
        {
            "rule": item["key"],
            "message": item["description"],
            "file": Path(item["file"]).resolve().relative_to(folder.resolve()).as_posix()
            if Path(item["file"]).is_absolute()
            else item["file"],
            "line": item["start"]["row"],
            "column": item["start"]["col"],
            "severity": item.get("severity", "Error"),
        }
        for item in raw
    ]
    issues.sort(key=lambda i: (i["file"], i["line"], i["rule"]))
    return {"available": True, "issues": issues, "count": len(issues)}


def lint_source(source: str) -> dict[str, Any]:
    """Lint a snippet that is not saved anywhere yet, with the default rule set."""
    with tempfile.TemporaryDirectory(prefix="abap-mcp-") as tmp:
        folder = Path(tmp)
        (folder / "src").mkdir()
        (folder / "src" / _snippet_filename(source)).write_text(source, encoding="utf-8")
        config = folder / "abaplint.json"
        config.write_text(json.dumps(DEFAULT_LINT_CONFIG), encoding="utf-8")
        result = _run_abaplint(folder, config)
    result["config"] = "default"
    return result


def lint_project(workspace: Workspace, project: str = ".") -> dict[str, Any]:
    """Lint a project folder, using its own abaplint.json when it has one."""
    folder = workspace.resolve(project)
    own_config = folder / "abaplint.json"
    if own_config.is_file():
        result = _run_abaplint(folder, own_config)
        result["config"] = workspace.relative(own_config)
        prefix = workspace.relative(folder)
    else:
        source = workspace.source_folder(project)
        with tempfile.TemporaryDirectory(prefix="abap-mcp-") as tmp:
            staged = Path(tmp)
            shutil.copytree(source, staged / "src")
            config = staged / "abaplint.json"
            config.write_text(json.dumps(DEFAULT_LINT_CONFIG), encoding="utf-8")
            result = _run_abaplint(staged, config)
        result["config"] = "default"
        prefix = workspace.relative(source)
        for issue in result["issues"]:
            issue["file"] = issue["file"].removeprefix("src/")
    for issue in result["issues"]:
        issue["file"] = issue["file"] if prefix == "." else f"{prefix}/{issue['file']}"
    return result


_TEST_SUMMARY = re.compile(r"(\d+)\s*/\s*(\d+)\s+tests?\s+passed", re.IGNORECASE)
_FAILED_TEST = re.compile(r"^\s*FAIL\s+(.+)$", re.MULTILINE)


def summarize_test_output(output: str) -> dict[str, Any]:
    """Pull counts and failing test names out of an ABAP Unit run on Node.js."""
    summary: dict[str, Any] = {"failed_tests": [m.strip() for m in _FAILED_TEST.findall(output)]}
    match = _TEST_SUMMARY.search(output)
    if match:
        summary["tests_passed"], summary["tests_total"] = int(match.group(1)), int(match.group(2))
    return summary


def run_tests(workspace: Workspace, project: str, install: bool = False) -> dict[str, Any]:
    """Run ``npm test`` in a project set up with the abaplint transpiler.

    This is the layout used by projects that run ABAP Unit on Node.js
    (see https://github.com/jakkwi/SAP): ``npm test`` lints, transpiles and
    executes the unit tests, with no SAP system involved.
    """
    folder = workspace.resolve(project)
    if not (folder / "package.json").is_file():
        return {"ran": False, "error": f"'{project}' has no package.json; it is not set up to run tests on Node.js"}
    npm = shutil.which("npm")
    if npm is None:
        return {"ran": False, "error": "npm is not installed"}
    steps: list[list[str]] = []
    if install or not (folder / "node_modules").is_dir():
        steps.append([npm, "ci" if (folder / "package-lock.json").is_file() else "install", "--no-audit", "--no-fund"])
    steps.append([npm, "test"])
    log: list[str] = []
    for step in steps:
        try:
            completed = subprocess.run(
                step, cwd=folder, capture_output=True, text=True, timeout=TIMEOUT_SECONDS * 3, check=False
            )
        except subprocess.TimeoutExpired:
            return {"ran": True, "passed": False, "error": f"'{' '.join(step[1:])}' timed out"}
        log.append(completed.stdout + completed.stderr)
        if completed.returncode != 0:
            output = "".join(log)
            return {
                "ran": True,
                "passed": False,
                "step": " ".join(["npm", *step[1:]]),
                **summarize_test_output(output),
                "output": output[-4000:],
            }
    output = "".join(log)
    return {"ran": True, "passed": True, **summarize_test_output(output), "output": output[-4000:]}
