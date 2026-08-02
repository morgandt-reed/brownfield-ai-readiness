"""Text rendering. Pure functions from a scan result to a string.

No calculation happens here. Anything that looks like a derived number was
derived upstream, so that the text report and the JSON report cannot disagree.
"""

from __future__ import annotations

from .model import Archetype, RepoFacts, RubricReport, ScanResult, Support

_SUPPORT_LABEL = {
    Support.SUPPORTED: "supported",
    Support.END_OF_SUPPORT: "PAST END OF SUPPORT",
    Support.UNKNOWN: "not in the support table",
    Support.NOT_DECLARED: "not declared in the repository",
}


def _rule(width: int = 78) -> str:
    return "-" * width


def _columns(rows: list[tuple[str, ...]], gap: int = 2) -> list[str]:
    """Left-aligned fixed-width columns. Stable output for any input."""
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [
        (" " * gap).join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
        for row in rows
    ]


def render_archetype_map(scan: ScanResult) -> str:
    concentration = scan.concentration
    lines = [
        "ARCHETYPE MAP",
        f"  root: {scan.root}",
        "",
    ]
    rows: list[tuple[str, ...]] = [("Archetype", "Repos", "Repositories")]
    for archetype in scan.archetypes:
        rows.append(
            (
                archetype.label,
                str(len(archetype.repos)),
                ", ".join(repo.name for repo in archetype.repos),
            )
        )
    lines.extend("  " + line for line in _columns(rows))

    reuse = concentration.reuse_factor
    mean = concentration.mean_repos_per_archetype
    lines.extend(
        [
            "",
            f"  {concentration.repositories} repositories fall into "
            f"{concentration.archetypes} archetypes.",
        ]
    )
    if reuse is not None and mean is not None:
        lines.append(f"  Mean repositories per archetype: {mean:.2f}")
        lines.append(f"  Reuse factor: {reuse:.2f}")
        lines.append("  The reuse factor is the share of repositories that are not the first of")
        lines.append("  their archetype — the share whose onboarding can draw on work already")
        lines.append("  done. It is arithmetic over the grouping. It does not measure how much of")
        lines.append("  that work is genuinely reusable, which is a judgement about how alike")
        lines.append("  two repositories are beyond their build manifest.")

    if scan.skipped:
        lines.extend(["", "  Skipped — no recognised build manifest at the repository root:"])
        lines.extend(f"    {name}: {reason}" for name, reason in scan.skipped)
    return "\n".join(lines)


def _repo_block(repo: RepoFacts) -> list[str]:
    build, tests, ci, runtime = repo.build, repo.tests, repo.ci, repo.runtime

    if build.lockfile:
        lock = build.lockfile
    elif not build.lockfile_applicable:
        lock = "n/a — this build system has no lockfile"
    else:
        lock = "none"

    pinned = build.pinned_fraction
    pinning = (
        "no direct dependencies declared"
        if pinned is None
        else f"{build.pinned_dependencies}/{build.declared_dependencies} ({pinned:.0%})"
    )

    ratio = tests.test_to_source_ratio
    test_shape = f"{tests.test_files} test / {tests.source_files} source files"
    if ratio is not None:
        test_shape += f" — ratio {ratio:.2f}"

    if runtime.version is None:
        runtime_line = _SUPPORT_LABEL[runtime.support]
    else:
        runtime_line = f"{runtime.name} {runtime.version} ({runtime.declared_in}) — "
        runtime_line += _SUPPORT_LABEL[runtime.support]
        if runtime.end_of_support:
            runtime_line += f", end of support {runtime.end_of_support}"

    rows = [
        ("build manifests", ", ".join(build.manifests) or "none"),
        ("lockfile", lock),
        ("dependencies pinned", pinning),
        ("container build", ", ".join(build.container_build) or "none"),
        ("declared runtime", runtime_line),
        ("test files", test_shape),
        (
            "test command",
            f"{tests.test_command}  [{tests.test_command_basis}]"
            if tests.test_command
            else "could not be inferred",
        ),
        ("coverage config", ", ".join(tests.coverage_config) or "none"),
        (
            "CI",
            ", ".join(ci.configs) + (" — references tests" if ci.references_tests else "")
            if ci.configs
            else "none",
        ),
        ("analysis tooling", ", ".join(ci.analysis_tools) or "none"),
    ]
    return ["    " + line for line in _columns([(f"{k}:", v) for k, v in rows])]


def render_fact_sheets(scan: ScanResult) -> str:
    lines = ["PER-ARCHETYPE FACT SHEETS"]
    for archetype in scan.archetypes:
        count = len(archetype.repos)
        noun = "repository" if count == 1 else "repositories"
        lines.extend(["", _rule(), f"{archetype.label}  ({count} {noun})"])
        for repo in archetype.repos:
            lines.extend(["", f"  {repo.name}"])
            lines.extend(_repo_block(repo))
    return "\n".join(lines)


def _level_cell(level: int | None, name: str | None) -> str:
    return "  —" if level is None else f"L{level} {name}"


def render_rubric(report: RubricReport, scan: ScanResult) -> str:
    lines = [
        f"READINESS RUBRIC — {report.rubric_id} v{report.rubric_version} "
        f"(as of {report.rubric_as_of})",
        "",
        "ESTATE-LEVEL DIMENSIONS",
    ]
    for score in report.estate:
        lines.append(f"  {score.title}: {_level_cell(score.level, score.level_name).strip()}")
        lines.append(f"    {score.detail}")

    if report.repositories:
        dimension_titles = [s.dimension_id for s in report.repositories[0].scores]
        header = ("Repository", *(d.replace("_", " ") for d in dimension_titles))
        rows: list[tuple[str, ...]] = [header]
        for entry in report.repositories:
            rows.append((entry.repo, *(_level_cell(s.level, s.level_name) for s in entry.scores)))
        lines.extend(["", "PER-REPOSITORY DIMENSIONS"])
        lines.extend("  " + line for line in _columns(rows))

        lines.extend(["", "WORST LEVEL WITHIN EACH ARCHETYPE"])
        lines.append("  The binding repository, not the average one. An archetype is onboarded")
        lines.append("  against its weakest member, because that is the one that stops.")
        by_repo = {entry.repo: entry for entry in report.repositories}
        rows = [("Archetype", *(d.replace("_", " ") for d in dimension_titles))]
        for archetype in scan.archetypes:
            cells: list[str] = []
            for index in range(len(dimension_titles)):
                levels = [
                    by_repo[repo.name].scores[index].level
                    for repo in archetype.repos
                    if by_repo[repo.name].scores[index].level is not None
                ]
                if not levels:
                    cells.append("  —")
                    continue
                worst = min(levels)
                sample = next(
                    s
                    for repo in archetype.repos
                    for s in [by_repo[repo.name].scores[index]]
                    if s.level == worst
                )
                cells.append(_level_cell(worst, sample.level_name))
            rows.append((_short(archetype), *cells))
        lines.extend("  " + line for line in _columns(rows))

    lines.extend(
        [
            "",
            "NOT SCORED HERE",
            "  Dimensions marked — require human assessment. They are unscored, not zero:",
            "  treating an unasked question as a bad answer would let an assessment be",
            "  improved by declining to ask. There is also no composite score, on purpose.",
            "  Averaging a blocked dimension against three healthy ones ranks a blocked",
            "  estate above a mediocre unblocked one, which inverts the decision.",
        ]
    )
    return "\n".join(lines)


def _short(archetype: Archetype) -> str:
    key = archetype.key
    framework = key.framework or "none"
    return f"{key.language}/{key.build_system}/{framework}"


def render_scan(scan: ScanResult, report: RubricReport | None = None) -> str:
    blocks = [render_archetype_map(scan), render_fact_sheets(scan)]
    if report is not None:
        blocks.append(render_rubric(report, scan))
    blocks.append(
        "\n".join(
            [
                "WHAT THIS SCAN DID NOT DO",
                "  It did not run a build, run a test, resolve a dependency or open a network",
                "  connection. Every line above is file evidence. Runtime support was judged",
                f"  against a table dated {scan.support_table_as_of}, not against today.",
                "  See the README section 'What the scanner cannot tell you'.",
            ]
        )
    )
    return "\n\n".join(blocks) + "\n"
