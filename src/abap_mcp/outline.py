"""Build a structural outline of ABAP classes and interfaces.

The outline is what an agent needs before it edits a class: which methods
exist, their visibility and signature, what is tested, and where each method
body starts and ends.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from abap_mcp.source import Statement, split_statements

_PARAM_KINDS = ("IMPORTING", "EXPORTING", "CHANGING", "RETURNING", "RAISING", "EXCEPTIONS")
_PARAM_NAME = re.compile(r"^(?:VALUE|REFERENCE)\((!?[\w/]+)\)$|^(!?[\w/]+)$", re.IGNORECASE)


@dataclass
class Method:
    name: str
    visibility: str
    static: bool = False
    abstract: bool = False
    redefinition: bool = False
    for_testing: bool = False
    importing: list[str] = field(default_factory=list)
    exporting: list[str] = field(default_factory=list)
    changing: list[str] = field(default_factory=list)
    returning: str | None = None
    raising: list[str] = field(default_factory=list)
    documented: bool = False
    declared_at: int = 0
    implemented_at: tuple[int, int] | None = None
    statements: int = 0


@dataclass
class ClassInfo:
    name: str
    kind: str  # "class" or "interface"
    public: bool = False
    final: bool = False
    abstract: bool = False
    for_testing: bool = False
    superclass: str | None = None
    interfaces: list[str] = field(default_factory=list)
    attributes: list[dict[str, Any]] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    documented: bool = False
    line: int = 0

    def method(self, name: str) -> Method | None:
        lowered = name.lower()
        return next((m for m in self.methods if m.name.lower() == lowered), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _words(statement: Statement) -> list[str]:
    return statement.text.rstrip(":").replace(":", " ").split()


_TYPE_MODIFIERS = {
    "REF",
    "TO",
    "STANDARD",
    "SORTED",
    "HASHED",
    "INDEX",
    "ANY",
    "TABLE",
    "OF",
    "RANGE",
    "LINE",
}
_AFTER_TYPE = {"OPTIONAL", "WITH", "EMPTY", "KEY", "UNIQUE", "NON-UNIQUE", "PREFERRED", "PARAMETER"}
_METHOD_FLAGS = {"FOR", "TESTING", "ABSTRACT", "FINAL", "REDEFINITION", "DEFAULT", "IGNORE"}


def _parse_signature(method: Method, words: list[str]) -> None:
    """Collect parameter names, skipping the type that follows each one.

    ``IMPORTING a TYPE REF TO zif_x b TYPE STANDARD TABLE OF t WITH EMPTY KEY``
    yields ``a`` and ``b``: everything between TYPE and the type name is a
    modifier, and anything after the type name until the next name is a flag.
    """
    kind: str | None = None
    in_type = False
    skip_default_value = False
    for word in words:
        upper = word.upper()
        if skip_default_value:
            skip_default_value = False
            continue
        if upper in _PARAM_KINDS:
            kind, in_type = upper, False
            continue
        if kind is None:
            continue
        if kind in ("RAISING", "EXCEPTIONS"):
            resumable = re.fullmatch(r"RESUMABLE\(([\w/]+)\)", word, re.IGNORECASE)
            if resumable:
                method.raising.append(resumable.group(1).lower())
            elif upper != "RESUMABLE":
                method.raising.append(word.lower())
            continue
        if upper in ("TYPE", "LIKE"):
            in_type = True
            continue
        if in_type:
            if upper not in _TYPE_MODIFIERS:
                in_type = False  # this word was the type name
            continue
        if upper == "DEFAULT":
            skip_default_value = True
            continue
        if upper in _AFTER_TYPE or upper in _METHOD_FLAGS:
            continue
        match = _PARAM_NAME.match(word)
        if not match:
            continue
        name = (match.group(1) or match.group(2)).lstrip("!").lower()
        if kind == "IMPORTING":
            method.importing.append(name)
        elif kind == "EXPORTING":
            method.exporting.append(name)
        elif kind == "CHANGING":
            method.changing.append(name)
        elif kind == "RETURNING":
            method.returning = name


def _method_from(statement: Statement, visibility: str) -> Method:
    words = _words(statement)
    upper_words = [w.upper() for w in words]
    method = Method(
        name=words[1].lower(),
        visibility=visibility,
        static=upper_words[0] == "CLASS-METHODS",
        abstract="ABSTRACT" in upper_words,
        redefinition="REDEFINITION" in upper_words,
        for_testing="TESTING" in upper_words and "FOR" in upper_words,
        documented=bool(statement.abap_doc),
        declared_at=statement.start_line,
    )
    _parse_signature(method, words[2:])
    return method


def outline(source: str) -> list[ClassInfo]:
    """Return every class and interface defined or implemented in ``source``."""
    statements = split_statements(source)
    found: dict[str, ClassInfo] = {}
    current: ClassInfo | None = None
    visibility = "public"
    implementing: ClassInfo | None = None
    open_method: tuple[Method, int] | None = None
    body_count = 0

    for stmt in statements:
        words = _words(stmt)
        if not words:
            continue
        upper = [w.upper() for w in words]
        keyword = upper[0]

        if keyword == "CLASS" and len(upper) > 2 and upper[2] == "DEFINITION":
            if "DEFERRED" in upper or "LOAD" in upper:
                continue
            name = words[1].lower()
            info = found.setdefault(name, ClassInfo(name=name, kind="class"))
            info.public = "PUBLIC" in upper
            info.final = "FINAL" in upper
            info.abstract = "ABSTRACT" in upper
            info.for_testing = "TESTING" in upper
            info.documented = bool(stmt.abap_doc)
            info.line = stmt.start_line
            if "INHERITING" in upper:
                info.superclass = words[upper.index("INHERITING") + 2].lower()
            current, visibility = info, "public"
            continue

        if keyword == "INTERFACE" and len(upper) > 1 and "DEFERRED" not in upper and "LOAD" not in upper:
            name = words[1].lower()
            info = found.setdefault(name, ClassInfo(name=name, kind="interface"))
            info.public = "PUBLIC" in upper
            info.documented = bool(stmt.abap_doc)
            info.line = stmt.start_line
            current, visibility = info, "public"
            continue

        if keyword in ("ENDCLASS", "ENDINTERFACE"):
            current = None
            implementing = None
            continue

        if keyword == "CLASS" and len(upper) > 2 and upper[2] == "IMPLEMENTATION":
            name = words[1].lower()
            implementing = found.setdefault(name, ClassInfo(name=name, kind="class"))
            continue

        if implementing is not None:
            if keyword == "METHOD" and len(words) > 1:
                name = words[1].lower()
                method = implementing.method(name)
                if method is None:  # e.g. zif_x~method, implemented from an interface
                    method = Method(name=name, visibility="public")
                    implementing.methods.append(method)
                open_method, body_count = (method, stmt.start_line), 0
            elif keyword == "ENDMETHOD" and open_method is not None:
                method, start = open_method
                method.implemented_at = (start, stmt.end_line)
                method.statements = body_count
                open_method = None
            elif open_method is not None:
                body_count += 1
            continue

        if current is None:
            continue
        if keyword in ("PUBLIC", "PROTECTED", "PRIVATE") and upper[1:2] == ["SECTION"]:
            visibility = keyword.lower()
        elif keyword in ("METHODS", "CLASS-METHODS") and len(words) > 1:
            current.methods.append(_method_from(stmt, visibility))
        elif keyword == "INTERFACES" and len(words) > 1:
            current.interfaces.append(words[1].lower())
        elif keyword in ("DATA", "CLASS-DATA", "CONSTANTS") and len(words) > 1:
            current.attributes.append(
                {
                    "name": words[1].lower(),
                    "visibility": visibility,
                    "static": keyword != "DATA",
                    "constant": keyword == "CONSTANTS",
                    "read_only": "READ-ONLY" in upper,
                    "line": stmt.start_line,
                }
            )

    return list(found.values())
