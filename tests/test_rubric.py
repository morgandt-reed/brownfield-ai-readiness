"""The rubric file, the scorers, and the invariants that keep them honest."""

from __future__ import annotations

import pytest
import yaml

from brownfield_readiness.errors import RubricError
from brownfield_readiness.model import Support
from brownfield_readiness.rubric import (
    ESTATE_SCORERS,
    PINNING_THRESHOLD,
    REPO_SCORERS,
    Rubric,
    apply,
    default_rubric_path,
    load_rubric,
    score_archetype_concentration,
    score_buildability,
    score_guardrail_coverage,
    score_testability,
)
from brownfield_readiness.scan import scan_estate

from .conftest import FIXTURES, write

_MINIMAL_DIMENSION = """
  - id: adoption_readiness
    title: Adoption readiness
    scope: estate
    assessment: human
    question: Who agreed?
    levels:
      - {level: 0, name: none, definition: nobody}
      - {level: 1, name: some, definition: somebody}
"""


def _rubric_text(dimensions: str) -> str:
    return f"id: t\nversion: 1\nas_of: 2026-08-02\ndimensions:{dimensions}"


class TestTheShippedRubric:
    def test_it_loads(self, rubric: Rubric):
        assert rubric.id == "brownfield-agentic-readiness"
        assert rubric.version == 1

    def test_the_filename_matches_the_declared_version(self, rubric: Rubric):
        assert f"v{rubric.version}" in default_rubric_path().name

    def test_every_dimension_the_readme_names_is_present(self, rubric: Rubric):
        assert {d.id for d in rubric.dimensions} == {
            "buildability",
            "testability",
            "archetype_concentration",
            "guardrail_coverage",
            "data_governance_constraint",
            "adoption_readiness",
        }

    def test_two_dimensions_are_human_only_and_stay_that_way(self, rubric: Rubric):
        """The honesty this repository is built around, asserted rather than asserted-in-prose."""
        human = {d.id for d in rubric.dimensions if d.assessment == "human"}
        assert human == {"data_governance_constraint", "adoption_readiness"}
        for dimension in rubric.dimensions:
            if dimension.assessment == "human":
                assert dimension.machine_evidence == ()
                assert dimension.human_evidence

    def test_every_machine_dimension_also_names_what_it_cannot_see(self, rubric: Rubric):
        for dimension in rubric.dimensions:
            if dimension.assessment != "human":
                assert dimension.human_evidence, dimension.id

    def test_the_file_refuses_a_composite_score(self):
        raw = yaml.safe_load(default_rubric_path().read_text(encoding="utf-8"))
        assert raw["scoring_policy"]["composite"] == "refused"

    def test_every_level_definition_is_non_empty(self, rubric: Rubric):
        for dimension in rubric.dimensions:
            for level in dimension.levels:
                assert level.definition.strip()


class TestRubricValidation:
    def test_a_scorer_without_machine_evidence_is_rejected(self, tmp_path):
        text = _rubric_text(
            "\n  - id: buildability\n    title: B\n    scope: repository\n"
            "    assessment: mixed\n    question: q\n"
            "    levels:\n      - {level: 0, name: n, definition: d}\n"
        )
        with pytest.raises(RubricError, match="lists no machine evidence"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_a_human_dimension_that_claims_machine_evidence_is_rejected(self, tmp_path):
        text = _rubric_text(
            _MINIMAL_DIMENSION.replace(
                "    question: Who agreed?",
                "    question: Who agreed?\n    machine_evidence: [a file]",
            )
        )
        with pytest.raises(RubricError, match="lists machine evidence"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_a_human_dimension_with_a_registered_scorer_is_rejected(self, tmp_path):
        text = _rubric_text(
            _MINIMAL_DIMENSION.replace("id: adoption_readiness", "id: buildability").replace(
                "scope: estate", "scope: repository"
            )
        )
        with pytest.raises(RubricError, match="marked `human` but a scorer is registered"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_a_mixed_dimension_with_no_scorer_is_rejected(self, tmp_path):
        text = _rubric_text(
            "\n  - id: vibes\n    title: V\n    scope: repository\n"
            "    assessment: mixed\n    question: q\n    machine_evidence: [nothing]\n"
            "    levels:\n      - {level: 0, name: n, definition: d}\n"
        )
        with pytest.raises(RubricError, match="no scorer is registered"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_a_scorer_declared_at_the_wrong_scope_is_rejected(self, tmp_path):
        text = _rubric_text(
            "\n  - id: buildability\n    title: B\n    scope: estate\n"
            "    assessment: mixed\n    question: q\n    machine_evidence: [manifests]\n"
            "    levels:\n      - {level: 0, name: n, definition: d}\n"
        )
        with pytest.raises(RubricError, match="operates on the repository"):
            load_rubric(write(tmp_path, "r.yaml", text))

    @pytest.mark.parametrize(
        ("content", "match"),
        [
            ("[]", "must be a mapping"),
            ("id: t\nversion: 1\ndimensions: []\n", "missing `as_of`"),
            ("id: t\nversion: 1\nas_of: soon\ndimensions: []\n", "must be a date"),
            ("id: t\nversion: 1\nas_of: 2026-08-02\ndimensions: []\n", "declares no dimensions"),
        ],
    )
    def test_malformed_rubrics(self, tmp_path, content: str, match: str):
        with pytest.raises(RubricError, match=match):
            load_rubric(write(tmp_path, "r.yaml", content))

    def test_a_dimension_that_is_not_a_mapping(self, tmp_path):
        with pytest.raises(RubricError, match="must be a mapping"):
            load_rubric(write(tmp_path, "r.yaml", _rubric_text("\n  - a string\n")))

    def test_a_dimension_missing_a_key(self, tmp_path):
        with pytest.raises(RubricError, match="missing `levels`"):
            load_rubric(
                write(
                    tmp_path,
                    "r.yaml",
                    _rubric_text(
                        "\n  - id: x\n    title: X\n    scope: estate\n"
                        "    assessment: human\n    question: q\n"
                    ),
                )
            )

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [("scope", "galaxy", "has scope"), ("assessment", "vibes", "has assessment")],
    )
    def test_invalid_enumerations(self, tmp_path, field: str, value: str, match: str):
        text = _rubric_text(_MINIMAL_DIMENSION).replace(f"{field}: estate", f"{field}: {value}")
        text = text.replace(f"{field}: human", f"{field}: {value}")
        with pytest.raises(RubricError, match=match):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_levels_must_run_from_zero_with_no_gaps(self, tmp_path):
        text = _rubric_text(_MINIMAL_DIMENSION).replace(
            "level: 1, name: some", "level: 3, name: some"
        )
        with pytest.raises(RubricError, match="must run 0..n"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_a_malformed_level_entry(self, tmp_path):
        text = _rubric_text(_MINIMAL_DIMENSION).replace(
            "      - {level: 0, name: none, definition: nobody}\n", "      - just a string\n"
        )
        with pytest.raises(RubricError, match="levels\\[0\\] is malformed"):
            load_rubric(write(tmp_path, "r.yaml", text))

    def test_unreadable_and_invalid_files(self, tmp_path):
        with pytest.raises(RubricError, match="cannot read"):
            load_rubric(tmp_path / "absent.yaml")
        with pytest.raises(RubricError, match="not valid YAML"):
            load_rubric(write(tmp_path, "r.yaml", "id: [unclosed\n"))

    def test_lookup_failures(self, rubric: Rubric):
        with pytest.raises(RubricError, match="no dimension"):
            rubric.by_id("nonexistent")
        with pytest.raises(RubricError, match="has no level 9"):
            rubric.by_id("buildability").named(9)


class TestScorers:
    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("orders-api", 3),
            ("customer-portal", 3),
            ("notify-worker", 3),
            ("legacy-batch", 2),
            ("reporting-tool", 2),
            ("web-frontend", 2),
            ("inventory-api", 1),
            ("invoicing-api", 1),
        ],
    )
    def test_buildability(self, repo_by_name, repo: str, expected: int):
        assert score_buildability(repo_by_name(repo))[0] == expected

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("orders-api", 3),
            ("web-frontend", 3),
            ("customer-portal", 3),
            ("inventory-api", 2),
            ("notify-worker", 2),
            ("legacy-batch", 0),
            ("invoicing-api", 0),
            ("reporting-tool", 0),
        ],
    )
    def test_testability(self, repo_by_name, repo: str, expected: int):
        assert score_testability(repo_by_name(repo))[0] == expected

    def test_an_inferable_command_alone_does_not_lift_testability(self, repo_by_name):
        """`legacy-batch` has a valid `mvn -B test` and zero tests. It scores zero."""
        repo = repo_by_name("legacy-batch")
        assert repo.tests.test_command == "mvn -B test"
        assert score_testability(repo)[0] == 0

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("orders-api", 3),
            ("web-frontend", 3),
            ("customer-portal", 3),
            ("invoicing-api", 0),
            ("notify-worker", 0),
        ],
    )
    def test_guardrail_coverage(self, repo_by_name, repo: str, expected: int):
        assert score_guardrail_coverage(repo_by_name(repo))[0] == expected

    def test_guardrail_level_one_is_a_pipeline_that_ignores_tests(self, tmp_path, support_table):
        estate = tmp_path / "estate"
        repo = estate / "svc"
        write(repo, "go.mod", "module example.com/svc\n\ngo 1.22\n")
        write(repo, ".gitlab-ci.yml", "package:\n  script: go build ./...\n")
        result = scan_estate(estate, support_table)
        assert score_guardrail_coverage(result.repos[0]) == (
            1,
            "CI present (gitlab-ci); no reference to running tests",
        )

    def test_buildability_reports_the_pinning_threshold_it_applied(self, repo_by_name):
        level, detail = score_buildability(repo_by_name("inventory-api"))
        assert level == 1
        assert "1/4 dependencies pinned (25%)" in detail
        assert PINNING_THRESHOLD == 0.80

    def test_buildability_floor_for_an_unrecognised_repository(self, tmp_path, support_table):
        from brownfield_readiness.scan import scan_repository

        facts = scan_repository(tmp_path, support_table)
        assert score_buildability(facts) == (0, "no build manifest at the repository root")

    def test_concentration_bands(self, estate):
        level, detail = score_archetype_concentration(estate)
        assert level == 0
        assert "8 repositories across 7 archetypes; reuse factor 0.12" == detail

    def test_concentration_of_an_empty_estate_is_unscored_not_zero(self, tmp_path, support_table):
        estate = tmp_path / "estate"
        (estate / "notes").mkdir(parents=True)
        write(estate, "notes/README.md", "no manifest here")
        result = scan_estate(estate, support_table)
        assert score_archetype_concentration(result) == (None, "no repositories were scanned")

    @pytest.mark.parametrize(
        ("repos", "archetypes", "expected"),
        [(8, 2, 3), (8, 4, 2), (8, 6, 1), (8, 7, 0), (4, 1, 3)],
    )
    def test_band_boundaries(self, repos: int, archetypes: int, expected: int, monkeypatch):
        from brownfield_readiness.model import Concentration, ScanResult

        class Fake(ScanResult):
            @property
            def concentration(self):
                return Concentration(repositories=repos, archetypes=archetypes)

        fake = Fake(root="x", repos=(), archetypes=())
        assert score_archetype_concentration(fake)[0] == expected


class TestApply:
    def test_human_dimensions_are_unscored_not_zero(self, rubric, estate):
        report = apply(rubric, estate)
        human = {s.dimension_id: s for s in report.estate if s.assessment == "human"}
        assert set(human) == {"data_governance_constraint", "adoption_readiness"}
        for score in human.values():
            assert score.level is None
            assert score.level_name is None
            assert "requires human assessment" in score.detail

    def test_every_repository_gets_every_repository_dimension(self, rubric, estate):
        report = apply(rubric, estate)
        assert len(report.repositories) == len(estate.repos)
        for entry in report.repositories:
            assert [s.dimension_id for s in entry.scores] == [
                "buildability",
                "testability",
                "guardrail_coverage",
            ]

    def test_the_report_carries_the_rubric_identity(self, rubric, estate):
        report = apply(rubric, estate)
        assert report.rubric_id == rubric.id
        assert report.rubric_as_of == rubric.as_of.isoformat()

    def test_a_repository_scoped_human_dimension_is_unscored(self, tmp_path, estate):
        text = _rubric_text(
            "\n  - id: code_quality\n    title: Code quality\n    scope: repository\n"
            "    assessment: human\n    question: is it any good?\n"
            "    human_evidence: [read it]\n"
            "    levels:\n      - {level: 0, name: unknown, definition: nobody looked}\n"
        )
        report = apply(load_rubric(write(tmp_path, "r.yaml", text)), estate)
        assert all(entry.scores[0].level is None for entry in report.repositories)

    def test_scorer_registries_cover_exactly_the_non_human_dimensions(self, rubric):
        registered = set(REPO_SCORERS) | set(ESTATE_SCORERS)
        declared = {d.id for d in rubric.dimensions if d.assessment != "human"}
        assert registered == declared


def test_support_enum_values_are_stable():
    """These strings appear in JSON output that other tools may parse."""
    assert {member.value for member in Support} == {
        "supported",
        "end-of-support",
        "unknown",
        "not-declared",
    }


def test_fixture_estate_shape_is_what_the_readme_documents(estate):
    assert len(estate.repos) == 8
    assert len(estate.archetypes) == 7
    assert [name for name, _ in estate.skipped] == ["platform-docs"]
    assert {repo.name for repo in estate.repos} == {
        path.name for path in FIXTURES.iterdir() if path.is_dir() and path.name != "platform-docs"
    }
