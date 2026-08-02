"""Declared runtime versions, checked against a dated support table.

The scanner has no network access, so it cannot ask a registry how old a
dependency is. What it can do is read the runtime version a repository declares
for itself and compare it with a table of published end-of-support dates that is
committed, dated and carries a source URL per entry.

Two deliberate constraints follow from that.

The comparison is made against the table's own `as_of` date, not against the
clock. A scan is therefore reproducible: the same tree scanned next year gives
the same answer, and the answer changes when someone updates the table, which is
a reviewable commit rather than a silent drift. The cost is that a stale table
reports stale conclusions -- which is why the as-of date is printed in the report
rather than tucked away.

A runtime with no entry in the table is reported as `unknown`, never as
supported. The table is a list of what was looked up, not a list of what exists.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .detect import read_text
from .ecosystems import Ecosystem
from .errors import SupportTableError
from .model import RuntimeFacts, Support
from .resources import locate


def default_support_table() -> Path:
    return locate("data", "runtime-support-*.yaml", "--support-table", SupportTableError)


@dataclass(frozen=True)
class SupportEntry:
    runtime: str
    version: str
    end_of_support: date
    source: str
    note: str | None


@dataclass(frozen=True)
class SupportTable:
    as_of: date
    entries: tuple[SupportEntry, ...]

    def lookup(self, runtime: str, version: str) -> SupportEntry | None:
        for entry in self.entries:
            if entry.runtime == runtime and entry.version == version:
                return entry
        return None


def load_support_table(path: Path | None = None) -> SupportTable:
    source_path = path or default_support_table()
    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SupportTableError(f"cannot read support table {source_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SupportTableError(f"support table {source_path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise SupportTableError(f"support table {source_path} must be a mapping")
    as_of = raw.get("as_of")
    if not isinstance(as_of, date):
        raise SupportTableError(f"support table {source_path} needs a top-level `as_of` date")

    rows = raw.get("runtimes")
    if not isinstance(rows, list) or not rows:
        raise SupportTableError(f"support table {source_path} needs a non-empty `runtimes` list")

    entries: list[SupportEntry] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SupportTableError(f"runtimes[{index}] in {source_path} must be a mapping")
        required = ("runtime", "version", "end_of_support", "source")
        missing = [key for key in required if key not in row]
        if missing:
            raise SupportTableError(
                f"runtimes[{index}] in {source_path} is missing: {', '.join(missing)}"
            )
        if not isinstance(row["end_of_support"], date):
            raise SupportTableError(
                f"runtimes[{index}] in {source_path}: end_of_support must be a date"
            )
        if not str(row["source"]).startswith("http"):
            raise SupportTableError(
                f"runtimes[{index}] in {source_path}: source must be a URL, "
                "so a reader can check it"
            )
        entries.append(
            SupportEntry(
                runtime=str(row["runtime"]),
                version=str(row["version"]),
                end_of_support=row["end_of_support"],
                source=str(row["source"]),
                note=str(row["note"]) if row.get("note") else None,
            )
        )
    return SupportTable(as_of=as_of, entries=tuple(entries))


# --------------------------------------------------------------------------
# Reading the declared version out of a repository
# --------------------------------------------------------------------------

_PY_VERSION = re.compile(r"(\d+\.\d+)")
_MAVEN_JAVA = re.compile(
    r"<(?:java\.version|maven\.compiler\.(?:source|release|target)|release)>\s*([\d.]+)\s*</"
)
_GRADLE_JAVA = re.compile(
    r"(?:JavaVersion\.VERSION_|jvmToolchain\(|sourceCompatibility\s*=\s*)['\"]?(\d+)"
)
_DOTNET_TFM = re.compile(r"<TargetFrameworks?>\s*net([\d.]+)\s*</", re.IGNORECASE)
_GO_DIRECTIVE = re.compile(r"^go\s+(\d+\.\d+)", re.MULTILINE)


def declared_runtime(repo: Path, eco: Ecosystem | None) -> tuple[str, str, str] | None:
    """Return `(runtime, version, declared_in)` or `None` if nothing is declared."""
    if eco is None:
        return None
    reader = {
        "python-pyproject": _python_runtime,
        "python-requirements": _python_runtime,
        "maven": _maven_runtime,
        "gradle": _gradle_runtime,
        "node": _node_runtime,
        "go": _go_runtime,
        "dotnet": _dotnet_runtime,
    }.get(eco.id)
    return reader(repo) if reader else None


def _python_runtime(repo: Path) -> tuple[str, str, str] | None:
    pyproject = repo / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(read_text(pyproject))
        except tomllib.TOMLDecodeError:
            data = {}
        project = data.get("project")
        if isinstance(project, dict):
            requires = project.get("requires-python")
            if isinstance(requires, str):
                match = _PY_VERSION.search(requires)
                if match:
                    return ("python", match.group(1), "pyproject.toml requires-python")
    pinned = repo / ".python-version"
    if pinned.is_file():
        match = _PY_VERSION.search(read_text(pinned))
        if match:
            return ("python", match.group(1), ".python-version")
    return _from_dockerfile(repo, "python")


def _maven_runtime(repo: Path) -> tuple[str, str, str] | None:
    match = _MAVEN_JAVA.search(read_text(repo / "pom.xml"))
    if match:
        return ("java", _normalise_java(match.group(1)), "pom.xml")
    return None


def _gradle_runtime(repo: Path) -> tuple[str, str, str] | None:
    for name in ("build.gradle", "build.gradle.kts"):
        match = _GRADLE_JAVA.search(read_text(repo / name))
        if match:
            return ("java", _normalise_java(match.group(1)), name)
    return None


def _normalise_java(value: str) -> str:
    # Maven still accepts the pre-9 spelling: `1.8` is Java 8.
    if value.startswith("1.") and len(value) > 2:
        return value[2:]
    return value.split(".")[0]


def _node_runtime(repo: Path) -> tuple[str, str, str] | None:
    try:
        data = json.loads(read_text(repo / "package.json") or "{}")
    except json.JSONDecodeError:
        data = {}
    engines = data.get("engines") if isinstance(data, dict) else None
    if isinstance(engines, dict) and isinstance(engines.get("node"), str):
        match = re.search(r"(\d+)", engines["node"])
        if match:
            return ("node", match.group(1), "package.json engines.node")
    nvmrc = repo / ".nvmrc"
    if nvmrc.is_file():
        match = re.search(r"(\d+)", read_text(nvmrc))
        if match:
            return ("node", match.group(1), ".nvmrc")
    return _from_dockerfile(repo, "node")


def _go_runtime(repo: Path) -> tuple[str, str, str] | None:
    match = _GO_DIRECTIVE.search(read_text(repo / "go.mod"))
    return ("go", match.group(1), "go.mod") if match else None


def _dotnet_runtime(repo: Path) -> tuple[str, str, str] | None:
    for project in sorted(repo.glob("*.csproj")) + sorted(repo.glob("*.fsproj")):
        match = _DOTNET_TFM.search(read_text(project))
        if match:
            return ("dotnet", match.group(1), project.name)
    return None


def _from_dockerfile(repo: Path, image: str) -> tuple[str, str, str] | None:
    dockerfile = repo / "Dockerfile"
    if not dockerfile.is_file():
        return None
    match = re.search(
        rf"^FROM\s+{image}:(\d+(?:\.\d+)?)",
        read_text(dockerfile),
        re.MULTILINE | re.IGNORECASE,
    )
    if match:
        return (image, match.group(1), "Dockerfile base image")
    return None


def runtime_facts(repo: Path, eco: Ecosystem | None, table: SupportTable) -> RuntimeFacts:
    declared = declared_runtime(repo, eco)
    if declared is None:
        return RuntimeFacts(None, None, None, Support.NOT_DECLARED, None, None)

    name, version, where = declared
    entry = table.lookup(name, version)
    if entry is None:
        return RuntimeFacts(name, version, where, Support.UNKNOWN, None, None)

    support = Support.END_OF_SUPPORT if entry.end_of_support <= table.as_of else Support.SUPPORTED
    return RuntimeFacts(
        name=name,
        version=version,
        declared_in=where,
        support=support,
        end_of_support=entry.end_of_support.isoformat(),
        source=entry.source,
    )
