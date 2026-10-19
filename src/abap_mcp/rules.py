"""Clean ABAP convention checks that run on plain source text.

These checks are deliberately dependency-free: they work on a snippet an agent
has just generated, before it is saved anywhere and without Node.js. For a full
static analysis with type information use the ``lint`` tool, which runs abaplint.

Each rule cites the section of the public Clean ABAP style guide it enforces:
https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from typing import Any

from abap_mcp.outline import ClassInfo, outline
from abap_mcp.source import Statement, split_statements

GUIDE_URL = "https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md"


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    message: str
    suggestion: str
    guide_section: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Context:
    source: str
    lines: list[str]
    statements: list[Statement]
    classes: list[ClassInfo]
    max_method_statements: int
    max_line_length: int


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    guide_section: str
    check: Callable[[Context], Iterator[Finding]]

    def describe(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "guide_section": self.guide_section}


RULES: list[Rule] = []


def rule(rule_id: str, title: str, guide_section: str) -> Callable[..., Any]:
    """Register a check. Rules are plain generator functions over a Context."""

    def register(func: Callable[[Context], Iterator[tuple[int, str, str]]]) -> Callable[..., Any]:
        def check(ctx: Context) -> Iterator[Finding]:
            for line, message, suggestion in func(ctx):
                yield Finding(rule_id, line, message, suggestion, guide_section)

        RULES.append(Rule(rule_id, title, guide_section, check))
        return func

    return register


_HUNGARIAN = re.compile(r"^<?(?:[lgmiecr][vstorfa]|fs|l)_\w+", re.IGNORECASE)
_DECLARATION = re.compile(r"^(?:DATA|CLASS-DATA|STATICS|FIELD-SYMBOLS|CONSTANTS)\b:?\s*(.*)$", re.IGNORECASE)
_INLINE = re.compile(r"\b(?:DATA|FINAL|FIELD-SYMBOL)\((<?[\w/]+>?)\)", re.IGNORECASE)


def _declared_names(stmt: Statement) -> Iterator[str]:
    match = _DECLARATION.match(stmt.text)
    if match:
        for part in match.group(1).split(","):
            words = part.split()
            if words and words[0].upper() not in ("BEGIN", "END"):
                yield words[0]
    yield from _INLINE.findall(stmt.text)


@rule(
    "no-hungarian-notation",
    "Avoid encodings, especially Hungarian notation and prefixes",
    "Avoid encodings, esp. Hungarian notation and prefixes",
)
def _no_hungarian(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for stmt in ctx.statements:
        names = list(_declared_names(stmt))
        if stmt.keyword in ("METHODS", "CLASS-METHODS"):
            names += [
                n
                for cls in ctx.classes
                for m in cls.methods
                if m.declared_at == stmt.start_line
                for n in (*m.importing, *m.exporting, *m.changing, *([m.returning] if m.returning else []))
            ]
        for name in names:
            if _HUNGARIAN.match(name):
                bare = re.sub(r"^<?(?:[a-z]{1,2})_", "", name, flags=re.IGNORECASE).rstrip(">")
                yield (
                    stmt.start_line,
                    f"'{name}' encodes its scope or type in a prefix",
                    f"Name it for what it holds, e.g. '{bare.lower()}'",
                )


_OBSOLETE: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^MOVE\s+(?!-)", re.I), "MOVE", "Use an assignment: target = source."),
    (re.compile(r"^COMPUTE\b", re.I), "COMPUTE", "Drop COMPUTE and write the assignment directly."),
    (re.compile(r"^ADD\s+.+\s+TO\s+", re.I), "ADD ... TO", "Use x += y or x = x + y."),
    (re.compile(r"^SUBTRACT\s+.+\s+FROM\s+", re.I), "SUBTRACT ... FROM", "Use x -= y."),
    (re.compile(r"^MULTIPLY\s+.+\s+BY\s+", re.I), "MULTIPLY ... BY", "Use x *= y."),
    (re.compile(r"^DIVIDE\s+.+\s+BY\s+", re.I), "DIVIDE ... BY", "Use x /= y."),
    (re.compile(r"^REFRESH\b", re.I), "REFRESH", "Use CLEAR on the table."),
    (re.compile(r"^DESCRIBE\s+TABLE\b.*\bLINES\b", re.I), "DESCRIBE TABLE ... LINES", "Use lines( itab )."),
    (
        re.compile(r"^CALL\s+METHOD\s+[\w~>=-]+(?:\s|$)(?!.*\()", re.I),
        "CALL METHOD",
        "Use a functional call: obj->method( ... ).",
    ),
    (re.compile(r"^(?:FORM|PERFORM)\b", re.I), "FORM/PERFORM", "Move the logic into a method of a class."),
    (
        re.compile(r"\bWITH\s+HEADER\s+LINE\b", re.I),
        "WITH HEADER LINE",
        "Declare a separate work area or use inline declarations.",
    ),
    (re.compile(r"\bOCCURS\b", re.I), "OCCURS", "Declare tables with TYPE STANDARD TABLE OF ... WITH EMPTY KEY."),
]


@rule(
    "no-obsolete-statements",
    "Prefer modern language elements to obsolete statements",
    "Prefer functional to procedural language constructs",
)
def _no_obsolete(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for stmt in ctx.statements:
        for pattern, label, suggestion in _OBSOLETE:
            if pattern.search(stmt.text):
                yield stmt.start_line, f"'{label}' is obsolete", suggestion
                break


@rule("prefer-is-not", "Prefer IS NOT to NOT IS", "Prefer IS NOT to NOT IS")
def _prefer_is_not(ctx: Context) -> Iterator[tuple[int, str, str]]:
    pattern = re.compile(r"\bNOT\s+([\w\-~>]+(?:\([^)]*\))?)\s+IS\s+", re.I)
    for stmt in ctx.statements:
        match = pattern.search(stmt.text)
        if match:
            yield stmt.start_line, "Negation placed before the operand", f"Write '{match.group(1)} IS NOT ...'"


@rule("method-length", "Keep methods small", "Keep methods small")
def _method_length(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for cls in ctx.classes:
        for method in cls.methods:
            if method.implemented_at and method.statements > ctx.max_method_statements:
                yield (
                    method.implemented_at[0],
                    f"Method '{method.name}' has {method.statements} statements (limit {ctx.max_method_statements})",
                    "Extract cohesive steps into private methods with intention-revealing names",
                )


@rule("line-length", "Stick to a reasonable line length", "Stick to a reasonable line length")
def _line_length(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for number, text in enumerate(ctx.lines, start=1):
        if len(text) > ctx.max_line_length:
            yield (
                number,
                f"Line is {len(text)} characters (limit {ctx.max_line_length})",
                "Break the statement over several lines",
            )


@rule("prefer-returning", "Prefer RETURNING to EXPORTING", "Prefer RETURNING to EXPORTING")
def _prefer_returning(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for cls in ctx.classes:
        for method in cls.methods:
            if len(method.exporting) == 1 and not method.changing and method.returning is None:
                yield (
                    method.declared_at,
                    f"Method '{method.name}' exports a single value",
                    f"Return it instead: RETURNING VALUE({method.exporting[0]}) TYPE ...",
                )


@rule("no-empty-catch", "Don't ignore exceptions", "Don't ignore exceptions")
def _no_empty_catch(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for current, following in itertools.pairwise(ctx.statements):
        if current.keyword == "CATCH" and following.keyword in ("ENDTRY", "CATCH", "CLEANUP"):
            yield (
                current.start_line,
                "Exception is caught and silently dropped",
                "Handle it, log it, or let it propagate",
            )


@rule("document-public-api", "Document public methods with ABAP Doc", "Add ABAP Doc only for public APIs")
def _document_public_api(ctx: Context) -> Iterator[tuple[int, str, str]]:
    for cls in ctx.classes:
        if not cls.public:
            continue
        for method in cls.methods:
            if (
                method.visibility == "public"
                and method.declared_at
                and not method.documented
                and method.name != "constructor"
            ):
                yield (
                    method.declared_at,
                    f"Public method '{method.name}' has no ABAP Doc",
                    'Add a "! comment describing behaviour and parameters',
                )


def check(source: str, *, max_method_statements: int = 40, max_line_length: int = 120) -> list[Finding]:
    """Run every registered rule against ``source`` and return findings by line."""
    ctx = Context(
        source=source,
        lines=source.splitlines(),
        statements=split_statements(source),
        classes=outline(source),
        max_method_statements=max_method_statements,
        max_line_length=max_line_length,
    )
    findings = [finding for registered in RULES for finding in registered.check(ctx)]
    return sorted(findings, key=lambda f: (f.line, f.rule))
