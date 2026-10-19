"""Locate ABAP objects in an abapGit-serialised folder, safely.

Every path a tool receives comes from a language model, so it is treated as
untrusted: it must resolve inside the workspace root the server was started
with. ``../../etc/passwd`` and symlinks pointing outside the root are rejected.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

OBJECT_TYPES = {
    "clas": "class",
    "intf": "interface",
    "prog": "program",
    "fugr": "function group",
    "devc": "package",
    "tabl": "table",
    "dtel": "data element",
    "doma": "domain",
    "ttyp": "table type",
    "msag": "message class",
    "xslt": "transformation",
    "ddls": "CDS view",
}

_FILE = re.compile(r"^(?P<name>[^.]+)\.(?P<type>[a-z]{4})(?:\.(?P<part>[\w.]+?))?\.(?P<ext>abap|xml|acds|asddls)$")


class WorkspaceError(ValueError):
    """Raised for a path outside the workspace or a missing object."""


@dataclass
class AbapObject:
    name: str
    type: str
    type_label: str
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Workspace:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise WorkspaceError(f"Workspace root does not exist: {self.root}")

    def resolve(self, relative: str = ".") -> Path:
        """Resolve a model-supplied path, refusing anything outside the root."""
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise WorkspaceError(f"Path '{relative}' is outside the workspace")
        if not candidate.exists():
            raise WorkspaceError(f"Path '{relative}' does not exist")
        return candidate

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def source_folder(self, project: str = ".") -> Path:
        """The folder holding serialised objects, honouring .abapgit.xml STARTING_FOLDER."""
        base = self.resolve(project)
        config = base / ".abapgit.xml"
        if config.is_file():
            starting = ET.parse(config).findtext(".//STARTING_FOLDER") or "/src/"
            folder = (base / starting.strip("/")).resolve()
            if folder.is_dir() and (folder == self.root or self.root in folder.parents):
                return folder
        return base / "src" if (base / "src").is_dir() else base

    def objects(self, project: str = ".") -> list[AbapObject]:
        found: dict[tuple[str, str], AbapObject] = {}
        folder = self.source_folder(project)
        for path in sorted(folder.rglob("*")):
            match = _FILE.match(path.name)
            if not path.is_file() or not match:
                continue
            object_type = match["type"]
            name = match["name"].replace("#", "/").upper()
            key = (name, object_type)
            obj = found.setdefault(
                key, AbapObject(name, object_type.upper(), OBJECT_TYPES.get(object_type, object_type))
            )
            obj.files.append(self.relative(path))
        return list(found.values())

    def find(self, name: str, project: str = ".") -> AbapObject:
        wanted = name.strip().upper()
        for obj in self.objects(project):
            if obj.name == wanted:
                return obj
        raise WorkspaceError(f"Object '{name}' not found under '{project}'")

    def read_source(self, obj: AbapObject) -> dict[str, str]:
        """Return ``{relative_path: text}`` for every .abap file of an object."""
        return {path: (self.root / path).read_text(encoding="utf-8") for path in obj.files if path.endswith(".abap")}
