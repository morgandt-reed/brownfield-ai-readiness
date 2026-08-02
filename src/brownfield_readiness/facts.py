"""Per-repository fact gathering.

Every function here answers a question of the form "is there evidence on disk
that X exists". None of them answers "does X work". The scanner never runs a
build, never runs a test, never resolves a dependency and never opens a network
connection, which means each of these facts is a *presence* signal and the
report has to say so in those words. A repository with a `tests/` directory
containing one skipped assertion scores exactly the same here as one with a real
suite, and pretending otherwise would make the tool worse than useless -- it
would make it confidently wrong about the single dimension that matters most.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .detect import count_dependencies, manifest_paths, matching_ecosystems, read_text
from .ecosystems import (
    ANALYSIS_MARKERS,
    CI_MARKERS,
    CONTAINER_BUILD_FILES,
    COVERAGE_MARKERS,
    IGNORED_DIRS,
    Ecosystem,
)
from .model import BuildFacts, CIFacts, TestFacts

# npm writes this into a generated package.json. It is the absence of a test
# command wearing the costume of one, and counting it would overstate the
# estate's testability in exactly the way this repository argues against.
_NPM_TEST_PLACEHOLDER = "no test specified"


def iter_files(repo: Path) -> list[Path]:
    """Every file under `repo`, skipping vendored and generated directories."""
    collected: list[Path] = []
    stack = [repo]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name not in IGNORED_DIRS:
                    stack.append(child)
            elif child.is_file():
                collected.append(child)
    return sorted(collected)


@lru_cache(maxsize=256)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a `**`-aware glob into a regex anchored at the repository root.

    `Path.full_match` would do this, but it arrived in 3.13 and this package
    supports 3.11. `fnmatch` is not a substitute: it lets `*` cross directory
    separators, which would make `**/test_*.py` and `*/test_*.py` the same
    pattern and silently over-count.
    """
    parts = pattern.split("/")
    regex = ""
    for index, part in enumerate(parts):
        if part == "**":
            regex += "(?:[^/]+/)*"
            continue
        for char in part:
            if char == "*":
                regex += "[^/]*"
            elif char == "?":
                regex += "[^/]"
            else:
                regex += re.escape(char)
        if index != len(parts) - 1:
            regex += "/"
    return re.compile(f"^{regex}$")


def _matches(relative: Path, globs: tuple[str, ...]) -> bool:
    text = relative.as_posix()
    return any(_glob_regex(pattern).match(text) for pattern in globs)


def count_source_and_test_files(repo: Path, eco: Ecosystem | None) -> tuple[int, int]:
    """Return `(source_files, test_files)` for the primary ecosystem's languages.

    A file counted as a test is not counted as source. The ratio between the two
    is the only "coverage-like" number this tool produces, and it is a ratio of
    *files*, which is a much weaker thing than a coverage percentage. It is
    reported because it separates "there is a token test directory" from "tests
    were written alongside the code", and for nothing beyond that.
    """
    if eco is None:
        return 0, 0
    source = tests = 0
    for path in iter_files(repo):
        relative = path.relative_to(repo)
        if _matches(relative, eco.test_globs):
            tests += 1
        elif _matches(relative, eco.source_globs):
            source += 1
    return source, tests


def container_build_files(repo: Path) -> tuple[str, ...]:
    return tuple(name for name in CONTAINER_BUILD_FILES if (repo / name).is_file())


def collect_build_facts(repo: Path, eco: Ecosystem | None) -> BuildFacts:
    manifests: list[str] = []
    for candidate in matching_ecosystems(repo):
        manifests.extend(str(path.relative_to(repo)) for path in manifest_paths(repo, candidate))

    lockfile = None
    applicable = False
    if eco is not None:
        applicable = eco.lockfile_applicable
        for name in eco.lockfiles:
            if (repo / name).is_file():
                lockfile = name
                break

    declared, pinned = count_dependencies(repo, eco) if eco else (0, 0)
    return BuildFacts(
        manifests=tuple(dict.fromkeys(manifests)),
        lockfile=lockfile,
        lockfile_applicable=applicable,
        declared_dependencies=declared,
        pinned_dependencies=pinned,
        container_build=container_build_files(repo),
    )


def coverage_config(repo: Path) -> tuple[str, ...]:
    found: list[str] = []
    for filename, needle, tool in COVERAGE_MARKERS:
        path = repo / filename
        if not path.is_file():
            continue
        if needle and needle not in read_text(path):
            continue
        found.append(tool)
    return tuple(dict.fromkeys(found))


def infer_test_command(repo: Path, eco: Ecosystem | None) -> tuple[str | None, str | None]:
    """Return `(command, basis)`, or `(None, None)` if nothing can be inferred.

    Worth reading carefully, because the two halves of this come apart. For Maven
    and Go the command exists because the toolchain defines a test phase, whether
    or not a single test has been written -- so an inferable command is *not*
    evidence that tests exist. For Python and Node the command has to be declared
    somewhere, so its absence is real evidence that nobody has written down how
    to run the suite. Both cases are reported with the basis that produced them
    so the difference stays visible.
    """
    if eco is None:
        return None, None

    if eco.id in {"python-pyproject", "python-requirements"}:
        haystack = "\n".join(
            read_text(repo / name)
            for name in ("pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini", "requirements.txt")
        )
        if "pytest" in haystack:
            return "pytest", "pytest declared in project configuration"
        if "nose" in haystack or "unittest" in haystack:
            return "python -m unittest discover", "unittest referenced in project configuration"
        return None, None

    if eco.id == "node":
        try:
            data = json.loads(read_text(repo / "package.json") or "{}")
        except json.JSONDecodeError:
            return None, None
        scripts = data.get("scripts") if isinstance(data, dict) else None
        command = scripts.get("test") if isinstance(scripts, dict) else None
        if isinstance(command, str) and _NPM_TEST_PLACEHOLDER not in command:
            return "npm test", f"package.json scripts.test = {command!r}"
        return None, None

    if eco.id == "maven":
        return "mvn -B test", "Maven lifecycle (exists whether or not tests do)"

    if eco.id == "gradle":
        wrapper = "./gradlew" if (repo / "gradlew").is_file() else "gradle"
        return f"{wrapper} test", "Gradle lifecycle (exists whether or not tests do)"

    if eco.id == "go":
        return "go test ./...", "Go toolchain (exists whether or not tests do)"

    if eco.id == "dotnet":
        return "dotnet test", "dotnet CLI (exists whether or not tests do)"

    if eco.id == "ruby":
        return "bundle exec rspec", "Bundler convention"

    if eco.id == "php":
        return "vendor/bin/phpunit", "Composer convention"

    return None, None


def collect_test_facts(repo: Path, eco: Ecosystem | None) -> TestFacts:
    source, tests = count_source_and_test_files(repo, eco)
    command, basis = infer_test_command(repo, eco)
    return TestFacts(
        test_files=tests,
        source_files=source,
        test_command=command,
        test_command_basis=basis,
        coverage_config=coverage_config(repo),
    )


def collect_ci_facts(repo: Path, tests: TestFacts) -> CIFacts:
    configs: list[str] = []
    texts: list[str] = []
    for marker, system in CI_MARKERS:
        path = repo / marker
        if path.is_dir():
            files = [p for p in sorted(path.iterdir()) if p.suffix in {".yml", ".yaml"}]
            if files:
                configs.append(system)
                texts.extend(read_text(p) for p in files)
        elif path.is_file():
            configs.append(system)
            texts.append(read_text(path))

    # A weak signal, deliberately kept weak. Matching the *first token* of the
    # inferred command was tried and rejected: for Go, Maven and Gradle that
    # token is the toolchain binary, so `go build ./...` read as "runs tests".
    # What is matched now is the word "test" anywhere in the pipeline definition,
    # or the whole inferred command -- which is what catches the runners whose
    # names do not contain the word, such as rspec and phpunit. A job merely
    # *named* "tests" still passes. The rubric level this feeds says the gate
    # appears to exist, never that it is enforced or that anyone reads it.
    blob = "\n".join(texts).lower()
    command = (tests.test_command or "").lower()
    references = bool(blob) and ("test" in blob or (bool(command) and command in blob))

    analysis = tuple(
        dict.fromkeys(tool for filename, tool in ANALYSIS_MARKERS if (repo / filename).exists())
    )
    return CIFacts(
        configs=tuple(dict.fromkeys(configs)),
        references_tests=references,
        analysis_tools=analysis,
    )
