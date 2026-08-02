"""JSON projection of a scan and a rubric report.

Separate from the text renderer and derived from the same value objects, so the
two output formats cannot disagree about a fact. Keys are stable and every
number that appears here also appears in the text report.
"""

from __future__ import annotations

from typing import Any

from .model import RepoFacts, RubricReport, ScanResult


def repo_to_dict(repo: RepoFacts) -> dict[str, Any]:
    return {
        "name": repo.name,
        "path": repo.path,
        "archetype": {
            "label": repo.archetype.label,
            "language": repo.archetype.language,
            "build_system": repo.archetype.build_system,
            "framework": repo.archetype.framework,
        },
        "build": {
            "manifests": list(repo.build.manifests),
            "lockfile": repo.build.lockfile,
            "lockfile_applicable": repo.build.lockfile_applicable,
            "declared_dependencies": repo.build.declared_dependencies,
            "pinned_dependencies": repo.build.pinned_dependencies,
            "pinned_fraction": repo.build.pinned_fraction,
            "container_build": list(repo.build.container_build),
        },
        "tests": {
            "test_files": repo.tests.test_files,
            "source_files": repo.tests.source_files,
            "test_to_source_ratio": repo.tests.test_to_source_ratio,
            "test_command": repo.tests.test_command,
            "test_command_basis": repo.tests.test_command_basis,
            "coverage_config": list(repo.tests.coverage_config),
        },
        "ci": {
            "configs": list(repo.ci.configs),
            "references_tests": repo.ci.references_tests,
            "analysis_tools": list(repo.ci.analysis_tools),
        },
        "runtime": {
            "name": repo.runtime.name,
            "version": repo.runtime.version,
            "declared_in": repo.runtime.declared_in,
            "support": repo.runtime.support.value,
            "end_of_support": repo.runtime.end_of_support,
            "source": repo.runtime.source,
        },
    }


def scan_to_dict(scan: ScanResult) -> dict[str, Any]:
    concentration = scan.concentration
    return {
        "root": scan.root,
        "support_table_as_of": scan.support_table_as_of,
        "concentration": {
            "repositories": concentration.repositories,
            "archetypes": concentration.archetypes,
            "reuse_factor": concentration.reuse_factor,
            "mean_repos_per_archetype": concentration.mean_repos_per_archetype,
        },
        "archetypes": [
            {
                "label": archetype.label,
                "language": archetype.key.language,
                "build_system": archetype.key.build_system,
                "framework": archetype.key.framework,
                "repositories": [repo.name for repo in archetype.repos],
            }
            for archetype in scan.archetypes
        ],
        "repositories": [repo_to_dict(repo) for repo in scan.repos],
        "skipped": [{"name": name, "reason": reason} for name, reason in scan.skipped],
        "evidence_basis": (
            "file presence only; no build, test, dependency resolution or network access"
        ),
    }


def report_to_dict(report: RubricReport) -> dict[str, Any]:
    def score(entry: Any) -> dict[str, Any]:
        return {
            "dimension": entry.dimension_id,
            "title": entry.title,
            "scope": entry.scope,
            "assessment": entry.assessment,
            # null, never 0. A dimension nobody assessed is not a dimension
            # scored badly, and a consumer that conflates them will rank an
            # unassessed estate above an honestly assessed one.
            "level": entry.level,
            "level_name": entry.level_name,
            "detail": entry.detail,
        }

    return {
        "rubric": {
            "id": report.rubric_id,
            "version": report.rubric_version,
            "as_of": report.rubric_as_of,
            "composite_score": None,
            "composite_rationale": (
                "refused: dimensions are not commensurable and a total would rank a "
                "blocked estate above a mediocre unblocked one"
            ),
        },
        "estate": [score(entry) for entry in report.estate],
        "repositories": [
            {
                "repository": entry.repo,
                "archetype": entry.archetype,
                "scores": [score(item) for item in entry.scores],
            }
            for entry in report.repositories
        ],
    }
