"""Frozen value types for a scan.

Nothing in this module reads a file, a clock or an environment variable. A
`ScanResult` is a description of what was found on disk at one moment; every
consumer downstream of it -- the rubric, the text renderer, the JSON writer --
is a pure function of that description. Keeping it that way is what makes the
golden-output test in CI meaningful rather than decorative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Support(str, Enum):
    """Where a declared runtime version sits against the shipped support table."""

    SUPPORTED = "supported"
    END_OF_SUPPORT = "end-of-support"
    UNKNOWN = "unknown"
    NOT_DECLARED = "not-declared"


@dataclass(frozen=True)
class ArchetypeKey:
    """What makes two repositories the same onboarding problem.

    Language and build system are the obvious part. The framework family is in
    here because it is where the harness work actually lands: two Maven
    repositories, one Spring Boot and one plain Java, share a build command and
    almost nothing else -- not the test scaffolding, not the configuration
    surface, not the conventions an agent has to be told about.
    """

    language: str
    build_system: str
    framework: str | None

    @property
    def label(self) -> str:
        framework = self.framework or "no framework detected"
        return f"{self.language} / {self.build_system} / {framework}"

    def sort_key(self) -> tuple[str, str, str]:
        return (self.language, self.build_system, self.framework or "~")


@dataclass(frozen=True)
class BuildFacts:
    """Signals about whether a build could be reproduced somewhere else."""

    manifests: tuple[str, ...]
    lockfile: str | None
    lockfile_applicable: bool
    declared_dependencies: int
    pinned_dependencies: int
    container_build: tuple[str, ...]

    @property
    def pinned_fraction(self) -> float | None:
        """Fraction of declared direct dependencies carrying an exact version.

        `None` rather than 1.0 when nothing is declared: a repository with no
        dependencies has not demonstrated pinning discipline, it has avoided the
        question, and averaging it in as a perfect score would flatter it.
        """
        if self.declared_dependencies == 0:
            return None
        return self.pinned_dependencies / self.declared_dependencies


@dataclass(frozen=True)
class TestFacts:
    """Signals about whether an oracle exists. Not about whether it is any good."""

    test_files: int
    source_files: int
    test_command: str | None
    test_command_basis: str | None
    coverage_config: tuple[str, ...]

    @property
    def test_to_source_ratio(self) -> float | None:
        if self.source_files == 0:
            return None
        return self.test_files / self.source_files


@dataclass(frozen=True)
class CIFacts:
    configs: tuple[str, ...]
    references_tests: bool
    analysis_tools: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeFacts:
    """A declared runtime version, checked against a dated support table."""

    name: str | None
    version: str | None
    declared_in: str | None
    support: Support
    end_of_support: str | None
    source: str | None


@dataclass(frozen=True)
class RepoFacts:
    name: str
    path: str
    archetype: ArchetypeKey
    build: BuildFacts
    tests: TestFacts
    ci: CIFacts
    runtime: RuntimeFacts


@dataclass(frozen=True)
class Archetype:
    key: ArchetypeKey
    repos: tuple[RepoFacts, ...]

    @property
    def label(self) -> str:
        return self.key.label


@dataclass(frozen=True)
class Concentration:
    """The estate-level arithmetic, and only the arithmetic.

    `reuse_factor` is the share of repositories that are *not* the first of their
    archetype -- that is, the share whose onboarding can draw on work already
    done for a sibling. It is a property of the grouping, not a measurement of
    anything. It says how many onboardings could reuse prior work, never how much
    of that work is actually reusable, which is a judgement about how alike two
    repositories are beyond their manifest.
    """

    repositories: int
    archetypes: int

    @property
    def reuse_factor(self) -> float | None:
        if self.repositories == 0:
            return None
        return 1.0 - (self.archetypes / self.repositories)

    @property
    def mean_repos_per_archetype(self) -> float | None:
        if self.archetypes == 0:
            return None
        return self.repositories / self.archetypes


@dataclass(frozen=True)
class DimensionScore:
    """One rubric dimension applied to one subject.

    `level is None` means the dimension requires human assessment. It is not a
    zero, and the renderer must never print it as one -- otherwise an assessment
    improves whenever a question goes unasked.
    """

    dimension_id: str
    title: str
    scope: str
    assessment: str
    level: int | None
    level_name: str | None
    detail: str


@dataclass(frozen=True)
class RepoScores:
    repo: str
    archetype: str
    scores: tuple[DimensionScore, ...]


@dataclass(frozen=True)
class RubricReport:
    rubric_id: str
    rubric_version: int
    rubric_as_of: str
    estate: tuple[DimensionScore, ...]
    repositories: tuple[RepoScores, ...]


@dataclass(frozen=True)
class ScanResult:
    root: str
    repos: tuple[RepoFacts, ...]
    archetypes: tuple[Archetype, ...]
    skipped: tuple[tuple[str, str], ...] = field(default=())
    support_table_as_of: str | None = None

    @property
    def concentration(self) -> Concentration:
        return Concentration(repositories=len(self.repos), archetypes=len(self.archetypes))
