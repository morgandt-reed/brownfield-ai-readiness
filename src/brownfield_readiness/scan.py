"""Walking a directory of repositories and grouping what is found.

The unit of input is a directory whose immediate children are checkouts. That is
a deliberate limitation rather than an oversight: an estate assessment starts
from an inventory someone has already cloned, and inferring repository
boundaries from an arbitrary tree produces confident nonsense on monorepos. If a
child is not recognisable as a project it is reported in a `skipped` list with
the reason, never dropped silently -- a scanner that quietly ignores a third of
the estate is worse than one that finds nothing.
"""

from __future__ import annotations

from pathlib import Path

from .detect import detect_ecosystem, detect_framework
from .errors import ScanError
from .facts import collect_build_facts, collect_ci_facts, collect_test_facts
from .model import Archetype, ArchetypeKey, RepoFacts, ScanResult
from .runtimes import SupportTable, load_support_table, runtime_facts


def scan_repository(repo: Path, table: SupportTable) -> RepoFacts:
    eco = detect_ecosystem(repo)
    archetype = (
        ArchetypeKey(
            language=eco.language,
            build_system=eco.build_system,
            framework=detect_framework(repo, eco),
        )
        if eco is not None
        else ArchetypeKey("unknown", "unknown", None)
    )
    tests = collect_test_facts(repo, eco)
    return RepoFacts(
        name=repo.name,
        path=str(repo),
        archetype=archetype,
        build=collect_build_facts(repo, eco),
        tests=tests,
        ci=collect_ci_facts(repo, tests),
        runtime=runtime_facts(repo, eco, table),
    )


def group_by_archetype(repos: tuple[RepoFacts, ...]) -> tuple[Archetype, ...]:
    """Group repositories by archetype, largest group first.

    Ties break on the archetype label so that the ordering is total and the
    output is byte-stable across runs and filesystems. A report whose row order
    changes between two scans of the same tree cannot be diffed, and a report
    that cannot be diffed cannot be put in CI.
    """
    buckets: dict[ArchetypeKey, list[RepoFacts]] = {}
    for repo in repos:
        buckets.setdefault(repo.archetype, []).append(repo)
    ordered = sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0].sort_key()))
    return tuple(
        Archetype(key=key, repos=tuple(sorted(members, key=lambda r: r.name)))
        for key, members in ordered
    )


def scan_estate(root: Path, table: SupportTable | None = None) -> ScanResult:
    """Scan every immediate subdirectory of `root` as one repository."""
    if not root.exists():
        raise ScanError(f"{root} does not exist")
    if not root.is_dir():
        raise ScanError(f"{root} is not a directory")

    support = table if table is not None else load_support_table()

    repos: list[RepoFacts] = []
    skipped: list[tuple[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if detect_ecosystem(child) is None:
            skipped.append((child.name, "no recognised build manifest at the repository root"))
            continue
        repos.append(scan_repository(child, support))

    if not repos and not skipped:
        raise ScanError(f"{root} contains no subdirectories to scan")

    return ScanResult(
        root=str(root),
        repos=tuple(repos),
        archetypes=group_by_archetype(tuple(repos)),
        skipped=tuple(skipped),
        support_table_as_of=support.as_of.isoformat(),
    )
