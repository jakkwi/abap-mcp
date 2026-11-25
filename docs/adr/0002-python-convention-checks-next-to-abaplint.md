# 0002. Own Clean ABAP checks in Python next to abaplint

## Status

Accepted

## Context

abaplint is the established static analyser for ABAP. It is thorough, but it needs Node.js, works on files in a project layout and starts a separate process per run. An agent that writes a method wants feedback on a snippet in a tight loop, before the code is saved anywhere, and sometimes on a machine without Node.js.

## Decision

`check_conventions` runs a small set of Clean ABAP rules written in Python ([`rules.py`](../../src/abap_mcp/rules.py)) on top of an own statement splitter ([`source.py`](../../src/abap_mcp/source.py)). It needs only the standard library and takes source text directly. `lint` stays available for full analysis through abaplint.

## Consequences

- Convention feedback is fast and works on unsaved snippets and without Node.js.
- Each finding carries a suggestion and the style guide section, which suits an agent better than a bare abaplint rule name.
- Some checks overlap with abaplint rules (obsolete statements, `IS NOT`, prefixes, method length), so the two tools can report the same problem in different words.
- The Python rules work on text, not on types. They can miss cases abaplint catches, and the statement splitter has to be kept correct for literals, templates and comments.
- A new rule is one decorated function plus a test.
