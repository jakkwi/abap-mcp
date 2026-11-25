# 0003. Run Node.js tooling as optional subprocesses

## Status

Accepted

## Context

abaplint and the ABAP Unit runner (abaplint transpiler with open-abap) exist only as Node.js packages. abap-mcp is a Python package. Requiring Node.js would block users who only need the pure-Python tools.

## Decision

[`tooling.py`](../../src/abap_mcp/tooling.py) calls `abaplint` and `npm` as subprocesses, with an argument list (no shell) and a timeout. Node.js is optional: when the tools are missing, `lint` and `run_tests` return a result that says so, and the other tools keep working. abaplint is looked up as `ABAP_MCP_ABAPLINT`, then `abaplint` on `PATH`, then `npx --yes @abaplint/cli@2`. The Docker image installs Node.js and `@abaplint/cli@2` so both tools work there out of the box.

## Consequences

- `pip install` stays small: the only Python dependency is the MCP SDK.
- Results depend on the installed abaplint version and on its JSON output format. Output that is not valid JSON shows up as an `error` in the `lint` result; renamed fields in that JSON would make the `lint` call fail.
- The npx fallback downloads `@abaplint/cli@2` from npm on first use, so it needs network access and trusts the npm registry. Installing abaplint globally or setting `ABAP_MCP_ABAPLINT` avoids that.
- `run_tests` executes the project's own `npm test` script and may run `npm ci` or `npm install`. That runs code from the project and its dependencies, so the tool is not marked read-only and should only be used on repositories the user trusts.
