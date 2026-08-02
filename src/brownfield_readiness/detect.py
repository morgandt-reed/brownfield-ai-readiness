"""Reading a repository's manifests to work out what it is.

Everything here is convention-matching on files that happen to be at the root of
a checkout. It is fast, it needs no toolchain installed, and it is wrong
whenever a repository does something unusual -- which brownfield repositories
regularly do. The detector's job is therefore to report *what it matched* rather
than to assert what the repository is, so that a reader who knows better can see
immediately where it went astray.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .ecosystems import ECOSYSTEMS, Ecosystem
from .model import ArchetypeKey

_UNKNOWN = ArchetypeKey(language="unknown", build_system="unknown", framework=None)


def read_text(path: Path) -> str:
    """Read a file, or return an empty string if it cannot be read as text.

    A binary blob named `pom.xml`, a broken symlink and a permission-denied file
    are all the same thing to a scanner: no evidence. None of them should stop a
    scan of two hundred repositories.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def manifest_paths(repo: Path, eco: Ecosystem) -> list[Path]:
    """Root-level manifest files for one ecosystem, in a stable order."""
    found: list[Path] = []
    for pattern in eco.manifests:
        if "*" in pattern:
            found.extend(sorted(p for p in repo.glob(pattern) if p.is_file()))
        else:
            candidate = repo / pattern
            if candidate.is_file():
                found.append(candidate)
    return found


def matching_ecosystems(repo: Path) -> list[Ecosystem]:
    """Every ecosystem whose manifests are present, in table order."""
    return [eco for eco in ECOSYSTEMS if manifest_paths(repo, eco)]


def detect_ecosystem(repo: Path) -> Ecosystem | None:
    """The primary ecosystem: the first match in table order.

    A repository can match several -- a Python service with a `package.json` for
    front-end assets, a Maven module with a helper `requirements.txt`. Picking
    one by a fixed precedence is a choice, not a deduction, and the fact sheet
    lists every manifest found so the choice can be second-guessed.
    """
    matches = matching_ecosystems(repo)
    return matches[0] if matches else None


def detect_framework(repo: Path, eco: Ecosystem) -> str | None:
    """The framework family, from dependency declarations.

    Node packages are matched against parsed dependency *names*; every other
    ecosystem is matched as a substring of the manifest text. The distinction is
    that `package.json` is reliably machine-readable and `pom.xml` variants are
    not worth a parser for this purpose.
    """
    if eco.id == "node":
        names = _node_dependency_names(repo / "package.json")
        for marker, family in eco.frameworks:
            if any(name == marker or name.startswith(marker) for name in names):
                return family
        return None

    blob = "\n".join(read_text(path) for path in manifest_paths(repo, eco)).lower()
    for marker, family in eco.frameworks:
        if marker.lower() in blob:
            return family
    return None


def detect_archetype(repo: Path) -> ArchetypeKey:
    eco = detect_ecosystem(repo)
    if eco is None:
        return _UNKNOWN
    return ArchetypeKey(
        language=eco.language,
        build_system=eco.build_system,
        framework=detect_framework(repo, eco),
    )


def _node_dependency_names(package_json: Path) -> list[str]:
    try:
        data = json.loads(read_text(package_json) or "{}")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    names: list[str] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            names.extend(str(key) for key in block)
    return names


# --------------------------------------------------------------------------
# Dependency pinning
#
# "Pinned" means one thing throughout: the declaration names an exact version,
# so two resolutions a month apart produce the same artefact. Ranges, wildcards
# and unbounded declarations are all unpinned, including the ones that are
# perfectly good practice in a library. This scanner is asking whether a build
# is reproducible, which is a different question from whether it is well
# maintained, and a library with `>=2.0` is deliberately answering "no".
# --------------------------------------------------------------------------

_MAVEN_DEPENDENCY = re.compile(r"<dependency>(.*?)</dependency>", re.DOTALL)
_MAVEN_VERSION = re.compile(r"<version>\s*([^<]+?)\s*</version>")
_GRADLE_DEPENDENCY = re.compile(
    r"""(?:implementation|api|compileOnly|runtimeOnly|testImplementation|"""
    r"""testRuntimeOnly|annotationProcessor)\s*[\(\s]\s*['"]([^'"]+)['"]"""
)
_DOTNET_PACKAGE = re.compile(r"<PackageReference\b([^>]*)>", re.IGNORECASE)
_DOTNET_VERSION = re.compile(r'Version\s*=\s*"([^"]+)"', re.IGNORECASE)
_GO_REQUIRE_LINE = re.compile(r"^\s*([\w./~-]+\.[\w./~-]+)\s+v\S+", re.MULTILINE)
_RUBY_GEM = re.compile(r"^\s*gem\s+['\"][^'\"]+['\"](.*)$", re.MULTILINE)
_EXACT_SEMVER = re.compile(r"^\d+(\.\d+)*$")


def count_dependencies(repo: Path, eco: Ecosystem) -> tuple[int, int]:
    """Return `(declared, pinned)` direct dependencies for the primary ecosystem."""
    handler = {
        "maven": _deps_maven,
        "gradle": _deps_gradle,
        "python-pyproject": _deps_pyproject,
        "python-requirements": _deps_requirements,
        "node": _deps_node,
        "go": _deps_go,
        "dotnet": _deps_dotnet,
        "ruby": _deps_ruby,
        "php": _deps_composer,
    }.get(eco.id)
    return handler(repo) if handler else (0, 0)


def _deps_maven(repo: Path) -> tuple[int, int]:
    blob = read_text(repo / "pom.xml")
    declared = pinned = 0
    for block in _MAVEN_DEPENDENCY.findall(blob):
        declared += 1
        match = _MAVEN_VERSION.search(block)
        if match and _is_literal_maven_version(match.group(1)):
            pinned += 1
    return declared, pinned


def _is_literal_maven_version(value: str) -> bool:
    # `${spring.version}` resolves from a property that may itself be a range or
    # come from a parent POM, so it is not evidence of pinning on its own.
    # Brackets and parentheses are Maven's range syntax; LATEST and RELEASE are
    # explicitly floating.
    if value.startswith("${"):
        return False
    if any(ch in value for ch in "[]()"):
        return False
    return value.upper() not in {"LATEST", "RELEASE"}


def _deps_gradle(repo: Path) -> tuple[int, int]:
    blob = ""
    for name in ("build.gradle", "build.gradle.kts"):
        blob += read_text(repo / name)
    declared = pinned = 0
    for coordinate in _GRADLE_DEPENDENCY.findall(blob):
        declared += 1
        parts = coordinate.split(":")
        if len(parts) >= 3 and parts[2] and "+" not in parts[2] and "$" not in parts[2]:
            pinned += 1
    return declared, pinned


def _deps_pyproject(repo: Path) -> tuple[int, int]:
    try:
        data = tomllib.loads(read_text(repo / "pyproject.toml"))
    except tomllib.TOMLDecodeError:
        return 0, 0
    specs: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        specs.extend(str(item) for item in project.get("dependencies", []) or [])
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                specs.extend(str(item) for item in group or [])
    poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
    if isinstance(poetry, dict):
        block = poetry.get("dependencies")
        if isinstance(block, dict):
            for name, constraint in block.items():
                if name == "python":
                    continue
                specs.append(f"{name}{constraint if isinstance(constraint, str) else ''}")
    return len(specs), sum(1 for spec in specs if "==" in spec)


def _deps_requirements(repo: Path) -> tuple[int, int]:
    declared = pinned = 0
    for line in read_text(repo / "requirements.txt").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith("-"):
            continue
        declared += 1
        if "==" in stripped:
            pinned += 1
    return declared, pinned


def _deps_node(repo: Path) -> tuple[int, int]:
    try:
        data = json.loads(read_text(repo / "package.json") or "{}")
    except json.JSONDecodeError:
        return 0, 0
    if not isinstance(data, dict):
        return 0, 0
    declared = pinned = 0
    for section in ("dependencies", "devDependencies"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for constraint in block.values():
            declared += 1
            if isinstance(constraint, str) and _EXACT_SEMVER.match(constraint.strip()):
                pinned += 1
    return declared, pinned


def _deps_go(repo: Path) -> tuple[int, int]:
    # Every `require` line in a go.mod names an exact version, and go.sum records
    # its hash. Go's answer to this question is "yes, by construction".
    count = len(_GO_REQUIRE_LINE.findall(read_text(repo / "go.mod")))
    return count, count


def _deps_dotnet(repo: Path) -> tuple[int, int]:
    declared = pinned = 0
    for project in sorted(repo.glob("*.csproj")) + sorted(repo.glob("*.fsproj")):
        for attributes in _DOTNET_PACKAGE.findall(read_text(project)):
            declared += 1
            version = _DOTNET_VERSION.search(attributes)
            if version and "*" not in version.group(1):
                pinned += 1
    return declared, pinned


def _deps_ruby(repo: Path) -> tuple[int, int]:
    declared = pinned = 0
    for tail in _RUBY_GEM.findall(read_text(repo / "Gemfile")):
        declared += 1
        constraint = re.search(r"['\"]([^'\"]+)['\"]", tail)
        if constraint and _EXACT_SEMVER.match(constraint.group(1).strip()):
            pinned += 1
    return declared, pinned


def _deps_composer(repo: Path) -> tuple[int, int]:
    try:
        data = json.loads(read_text(repo / "composer.json") or "{}")
    except json.JSONDecodeError:
        return 0, 0
    if not isinstance(data, dict):
        return 0, 0
    declared = pinned = 0
    for section in ("require", "require-dev"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, constraint in block.items():
            if name == "php":
                continue
            declared += 1
            if isinstance(constraint, str) and _EXACT_SEMVER.match(constraint.strip()):
                pinned += 1
    return declared, pinned
