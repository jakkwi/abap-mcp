"""Split ABAP source into statements.

ABAP statements end with a period. That is simple until periods, colons and
quotes turn up inside string literals, string templates and comments, which is
exactly where a naive ``split(".")`` falls over. This module walks the source
once, character by character, and keeps track of which of those contexts it is
in, so the rest of the package can reason about whole statements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Statement:
    """One ABAP statement, with comments removed and whitespace collapsed."""

    text: str
    start_line: int
    end_line: int
    abap_doc: tuple[str, ...] = field(default=())

    @property
    def keyword(self) -> str:
        """The first word of the statement, upper-cased (``METHODS``, ``DATA``...)."""
        head = self.text.split(" ", 1)[0].rstrip(":")
        return head.upper()

    @property
    def upper(self) -> str:
        return self.text.upper()


def split_statements(source: str) -> list[Statement]:
    """Return the statements in ``source`` in order.

    Full-line comments (``*`` in column one) and end-of-line comments (``"``)
    are dropped. ABAP Doc comments (``"!``) directly above a statement are kept
    and attached to it, because they are documentation rather than noise.
    """
    statements: list[Statement] = []
    buffer: list[str] = []
    start_line = 0
    pending_doc: list[str] = []
    doc_for_statement: list[str] = []

    quote: str | None = None  # "'", "`" or "|" while inside a literal or template
    brace_depth = 0  # embedded expressions inside a |template|

    for line_no, line in enumerate(source.splitlines(), start=1):
        if quote is None and not "".join(buffer).strip():
            stripped = line.lstrip()
            if stripped.startswith('"!'):
                pending_doc.append(stripped[2:].strip())
                continue
            if line.startswith("*") or stripped.startswith('"'):
                continue

        i = 0
        while i < len(line):
            char = line[i]

            if quote is not None:
                buffer.append(char)
                if quote == "|":
                    if char == "\\" and i + 1 < len(line):
                        buffer.append(line[i + 1])
                        i += 2
                        continue
                    if char == "{":
                        brace_depth += 1
                    elif char == "}":
                        brace_depth = max(0, brace_depth - 1)
                    elif char == "|" and brace_depth == 0:
                        quote = None
                elif char == quote:
                    if i + 1 < len(line) and line[i + 1] == quote:  # escaped '' or ``
                        buffer.append(line[i + 1])
                        i += 2
                        continue
                    quote = None
                i += 1
                continue

            if char == '"':  # end-of-line comment
                break
            if char in "'`|":
                if not "".join(buffer).strip():
                    start_line = line_no
                quote = char
                buffer.append(char)
                i += 1
                continue
            if char == ".":
                nxt = line[i + 1] if i + 1 < len(line) else " "
                if nxt.isspace() or nxt == '"':
                    text = _WHITESPACE.sub(" ", "".join(buffer)).strip()
                    if text:
                        statements.append(Statement(text, start_line, line_no, tuple(doc_for_statement)))
                    buffer = []
                    doc_for_statement = []
                    i += 1
                    continue
            if not char.isspace() and not "".join(buffer).strip():
                start_line = line_no
                doc_for_statement = pending_doc
                pending_doc = []
            buffer.append(char)
            i += 1

        if quote == "'" or quote == "`":
            quote = None  # character literals cannot span lines; recover gracefully
        buffer.append(" ")

    leftover = _WHITESPACE.sub(" ", "".join(buffer)).strip()
    if leftover:
        statements.append(Statement(leftover, start_line, len(source.splitlines()), tuple(doc_for_statement)))
    return statements
