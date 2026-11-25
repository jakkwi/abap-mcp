# 0001. Work on abapGit files, not a live SAP system

## Status

Accepted

## Context

ABAP code normally lives inside an SAP system. Tools that read it there need the ADT REST API, a user on that system and network access to it. Many developers and most AI agents have none of that on their laptop, and an SAP system is not something a CI runner can start.

abapGit serialises ABAP objects as plain files (`zcl_x.clas.abap`, `zcl_x.clas.xml`, ...) in a Git repository. Those files can be read, linted and, with the abaplint transpiler, even tested without SAP.

## Decision

abap-mcp reads only abapGit files under a workspace root on disk. It has no SAP connection, no SAP credentials and no SAP client library.

## Consequences

- It works offline, on a laptop, in CI and in a container, with no SAP licence or account.
- No secrets are needed to run it.
- It sees only what is committed as abapGit files. Objects that exist only in the system, runtime data and SAP standard code are invisible to it.
- `lint` understands only the types defined in the repository, plus what abaplint knows about the language. References to SAP standard objects can show up as unknown types.
- `run_tests` covers only projects set up to run ABAP Unit on Node.js. Tests that depend on the database or on SAP standard code cannot run.
