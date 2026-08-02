"""Loading the rubric and applying the machine-scorable part of it.

The rubric YAML is the specification and this module is one implementation of
it. They can drift, so the loader validates the structural claims the scorer
relies on -- that every dimension declaring machine evidence has a scorer
registered here, and that every level a scorer can return exists in the file
under the name the scorer uses. `tests/test_rubric.py` asserts the same
invariants, so the drift fails a build rather than producing a plausible report
against a rubric nobody has read.

The scorers are all threshold functions over facts gathered elsewhere. There is
no weighting, no normalisation and no total, for the reason set out in the
rubric's own `scoring_policy` block.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .errors import RubricError
from .model import DimensionScore, RepoFacts, RepoScores, RubricReport, ScanResult
from .resources import locate

# The share of direct dependencies that must carry an exact version for a build
# to count as pinned when no lockfile exists. A judgement, stated once here
# rather than buried in a comparison: below this, enough of the tree is floating
# that two resolutions a month apart are not the same build.
PINNING_THRESHOLD = 0.80

# Reuse-factor bands for archetype concentration. Round numbers, chosen for
# legibility rather than derived from anything; the underlying figure is printed
# alongside the level so a reader can apply their own bands.
CONCENTRATION_BANDS = ((0.75, 3), (0.50, 2), (0.25, 1))


def default_rubric_path() -> Path:
    return locate("rubric", "readiness-v*.yaml", "--rubric", RubricError)


@dataclass(frozen=True)
class Level:
    level: int
    name: str
    definition: str


@dataclass(frozen=True)
class Dimension:
    id: str
    title: str
    scope: str
    assessment: str
    question: str
    machine_evidence: tuple[str, ...]
    human_evidence: tuple[str, ...]
    levels: tuple[Level, ...]

    def named(self, level: int) -> Level:
        for candidate in self.levels:
            if candidate.level == level:
                return candidate
        raise RubricError(f"dimension {self.id} has no level {level}")


@dataclass(frozen=True)
class Rubric:
    id: str
    version: int
    as_of: date
    dimensions: tuple[Dimension, ...]

    def by_id(self, dimension_id: str) -> Dimension:
        for dimension in self.dimensions:
            if dimension.id == dimension_id:
                return dimension
        raise RubricError(f"no dimension {dimension_id} in rubric {self.id}")


_VALID_SCOPES = {"repository", "estate"}
_VALID_ASSESSMENTS = {"machine", "mixed", "human"}


def load_rubric(path: Path | None = None) -> Rubric:
    source = path or default_rubric_path()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RubricError(f"cannot read rubric {source}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RubricError(f"rubric {source} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise RubricError(f"rubric {source} must be a mapping")
    for key in ("id", "version", "as_of", "dimensions"):
        if key not in raw:
            raise RubricError(f"rubric {source} is missing `{key}`")
    if not isinstance(raw["as_of"], date):
        raise RubricError(f"rubric {source}: `as_of` must be a date")

    dimensions: list[Dimension] = []
    for index, item in enumerate(raw["dimensions"] or []):
        dimensions.append(_dimension(item, index, source))
    if not dimensions:
        raise RubricError(f"rubric {source} declares no dimensions")

    rubric = Rubric(
        id=str(raw["id"]),
        version=int(raw["version"]),
        as_of=raw["as_of"],
        dimensions=tuple(dimensions),
    )
    _check_scorers_match(rubric, source)
    return rubric


def _dimension(item: Any, index: int, source: Path) -> Dimension:
    if not isinstance(item, dict):
        raise RubricError(f"rubric {source}: dimensions[{index}] must be a mapping")
    for key in ("id", "title", "scope", "assessment", "question", "levels"):
        if key not in item:
            raise RubricError(f"rubric {source}: dimensions[{index}] is missing `{key}`")
    if item["scope"] not in _VALID_SCOPES:
        raise RubricError(f"rubric {source}: {item['id']} has scope {item['scope']!r}")
    if item["assessment"] not in _VALID_ASSESSMENTS:
        raise RubricError(f"rubric {source}: {item['id']} has assessment {item['assessment']!r}")

    levels: list[Level] = []
    for position, entry in enumerate(item["levels"] or []):
        if not isinstance(entry, dict) or not {"level", "name", "definition"} <= set(entry):
            raise RubricError(f"rubric {source}: {item['id']} levels[{position}] is malformed")
        levels.append(
            Level(
                level=int(entry["level"]),
                name=str(entry["name"]),
                definition=str(entry["definition"]).strip(),
            )
        )
    if [lvl.level for lvl in levels] != list(range(len(levels))):
        raise RubricError(f"rubric {source}: {item['id']} levels must run 0..n with no gaps")

    return Dimension(
        id=str(item["id"]),
        title=str(item["title"]),
        scope=str(item["scope"]),
        assessment=str(item["assessment"]),
        question=str(item["question"]).strip(),
        machine_evidence=tuple(str(x) for x in item.get("machine_evidence") or ()),
        human_evidence=tuple(str(x) for x in item.get("human_evidence") or ()),
        levels=tuple(levels),
    )


# --------------------------------------------------------------------------
# Scorers
# --------------------------------------------------------------------------

RepoScorer = Callable[[RepoFacts], tuple[int, str]]
EstateScorer = Callable[[ScanResult], tuple[int | None, str]]


def score_buildability(repo: RepoFacts) -> tuple[int, str]:
    build = repo.build
    if not build.manifests:
        return 0, "no build manifest at the repository root"

    pinned = build.pinned_fraction
    parts: list[str] = []
    if build.lockfile:
        parts.append(f"lockfile {build.lockfile}")
    elif build.lockfile_applicable:
        parts.append("no lockfile")
    else:
        parts.append("no lockfile concept in this build system")
    if pinned is None:
        parts.append("no direct dependencies declared")
    else:
        parts.append(
            f"{build.pinned_dependencies}/{build.declared_dependencies} "
            f"dependencies pinned ({pinned:.0%})"
        )

    fixed = build.lockfile is not None or (pinned is not None and pinned >= PINNING_THRESHOLD)
    if not fixed:
        return 1, "; ".join(parts)

    if build.container_build:
        parts.append(f"container build: {', '.join(build.container_build)}")
        return 3, "; ".join(parts)
    parts.append("no container or devcontainer build definition")
    return 2, "; ".join(parts)


def score_testability(repo: RepoFacts) -> tuple[int, str]:
    tests = repo.tests
    if tests.test_files == 0:
        return 0, "no files matched this ecosystem's test conventions"

    ratio = tests.test_to_source_ratio
    shape = f"{tests.test_files} test files / {tests.source_files} source files"
    if ratio is not None:
        shape += f" ({ratio:.2f})"

    if tests.test_command is None:
        return 1, f"{shape}; no test command could be inferred"

    detail = f"{shape}; `{tests.test_command}` ({tests.test_command_basis})"
    if tests.coverage_config and repo.ci.references_tests:
        return 3, f"{detail}; coverage: {', '.join(tests.coverage_config)}; referenced in CI"

    missing = []
    if not tests.coverage_config:
        missing.append("no coverage instrumentation configured")
    if not repo.ci.references_tests:
        missing.append("CI does not reference running tests")
    return 2, f"{detail}; {'; '.join(missing)}"


def score_guardrail_coverage(repo: RepoFacts) -> tuple[int, str]:
    ci = repo.ci
    if not ci.configs:
        return 0, "no CI configuration found in the repository"
    systems = ", ".join(ci.configs)
    if not ci.references_tests:
        return 1, f"CI present ({systems}); no reference to running tests"
    if ci.analysis_tools:
        return 3, f"CI present ({systems}); runs tests; analysis: {', '.join(ci.analysis_tools)}"
    return 2, f"CI present ({systems}); runs tests; no analysis tooling configured"


def score_archetype_concentration(scan: ScanResult) -> tuple[int | None, str]:
    concentration = scan.concentration
    reuse = concentration.reuse_factor
    if reuse is None:
        return None, "no repositories were scanned"
    detail = (
        f"{concentration.repositories} repositories across {concentration.archetypes} "
        f"archetypes; reuse factor {reuse:.2f}"
    )
    for threshold, level in CONCENTRATION_BANDS:
        if reuse >= threshold:
            return level, detail
    return 0, detail


REPO_SCORERS: dict[str, RepoScorer] = {
    "buildability": score_buildability,
    "testability": score_testability,
    "guardrail_coverage": score_guardrail_coverage,
}

ESTATE_SCORERS: dict[str, EstateScorer] = {
    "archetype_concentration": score_archetype_concentration,
}

HUMAN_ONLY_DETAIL = "requires human assessment — no signal for this exists in a repository"


def _check_scorers_match(rubric: Rubric, source: Path) -> None:
    """Fail loudly if the rubric file and this module disagree about what is automated."""
    for dimension in rubric.dimensions:
        registered = dimension.id in REPO_SCORERS or dimension.id in ESTATE_SCORERS
        if dimension.assessment == "human":
            if registered:
                raise RubricError(
                    f"rubric {source}: {dimension.id} is marked `human` but a scorer is registered"
                )
            if dimension.machine_evidence:
                raise RubricError(
                    f"rubric {source}: {dimension.id} is marked `human` but lists machine evidence"
                )
            continue
        if not registered:
            raise RubricError(
                f"rubric {source}: {dimension.id} is marked `{dimension.assessment}` "
                "but no scorer is registered for it"
            )
        if not dimension.machine_evidence:
            raise RubricError(
                f"rubric {source}: {dimension.id} has a scorer but lists no machine evidence"
            )
        expected_scope = "repository" if dimension.id in REPO_SCORERS else "estate"
        if dimension.scope != expected_scope:
            raise RubricError(
                f"rubric {source}: {dimension.id} has scope {dimension.scope!r} but its "
                f"scorer operates on the {expected_scope}"
            )


def _score(dimension: Dimension, level: int | None, detail: str) -> DimensionScore:
    return DimensionScore(
        dimension_id=dimension.id,
        title=dimension.title,
        scope=dimension.scope,
        assessment=dimension.assessment,
        level=level,
        level_name=dimension.named(level).name if level is not None else None,
        detail=detail,
    )


def apply(rubric: Rubric, scan: ScanResult) -> RubricReport:
    estate: list[DimensionScore] = []
    for dimension in rubric.dimensions:
        if dimension.scope != "estate":
            continue
        if dimension.assessment == "human":
            estate.append(_score(dimension, None, HUMAN_ONLY_DETAIL))
            continue
        level, detail = ESTATE_SCORERS[dimension.id](scan)
        estate.append(_score(dimension, level, detail))

    repository_dimensions = [d for d in rubric.dimensions if d.scope == "repository"]
    repositories: list[RepoScores] = []
    for repo in scan.repos:
        scores: list[DimensionScore] = []
        for dimension in repository_dimensions:
            if dimension.assessment == "human":
                scores.append(_score(dimension, None, HUMAN_ONLY_DETAIL))
                continue
            level, detail = REPO_SCORERS[dimension.id](repo)
            scores.append(_score(dimension, level, detail))
        repositories.append(
            RepoScores(repo=repo.name, archetype=repo.archetype.label, scores=tuple(scores))
        )

    return RubricReport(
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        rubric_as_of=rubric.as_of.isoformat(),
        estate=tuple(estate),
        repositories=tuple(repositories),
    )
