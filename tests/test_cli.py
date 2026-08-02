"""The command line, both output formats, and the golden files the README quotes."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from brownfield_readiness.cli import main
from brownfield_readiness.render import render_scan
from brownfield_readiness.rubric import apply
from brownfield_readiness.serialize import report_to_dict, scan_to_dict

from .conftest import FIXTURES, REPO_ROOT, write

GOLDEN = REPO_ROOT / "tests" / "golden"


@pytest.fixture
def run():
    runner = CliRunner()

    def _run(*args: str, expect_success: bool = True):
        result = runner.invoke(main, list(args))
        if expect_success and result.exit_code != 0:
            raise AssertionError(f"exit {result.exit_code}\n{result.output}\n{result.exception}")
        return result

    return _run


class TestGoldenOutput:
    """The README quotes these files verbatim.

    They are diffed against live CLI output in CI as well as here, so the README
    cannot drift away from the tool. A README that documents a command it no
    longer matches is worse than no README, because a reader has no way to tell
    which half is stale.
    """

    def test_scan_output_matches_the_committed_golden_file(self, estate):
        expected = (GOLDEN / "scan.txt").read_text(encoding="utf-8")
        assert render_scan(estate).replace(str(FIXTURES), "fixtures") == expected

    def test_score_output_matches_the_committed_golden_file(self, estate, rubric):
        expected = (GOLDEN / "score.txt").read_text(encoding="utf-8")
        rendered = render_scan(estate, apply(rubric, estate))
        assert rendered.replace(str(FIXTURES), "fixtures") == expected


class TestScanCommand:
    def test_text_output(self, run):
        result = run("scan", str(FIXTURES))
        assert "ARCHETYPE MAP" in result.output
        assert "PER-ARCHETYPE FACT SHEETS" in result.output
        assert "WHAT THIS SCAN DID NOT DO" in result.output

    def test_json_output_is_parseable_and_complete(self, run):
        payload = json.loads(run("scan", str(FIXTURES), "--format", "json").output)
        assert len(payload["repositories"]) == 8
        assert len(payload["archetypes"]) == 7
        assert payload["concentration"]["reuse_factor"] == pytest.approx(0.125)
        assert payload["skipped"] == [
            {
                "name": "platform-docs",
                "reason": "no recognised build manifest at the repository root",
            }
        ]
        assert "no build, test, dependency resolution or network" in payload["evidence_basis"]

    def test_json_and_text_agree_on_every_repository(self, run, estate):
        payload = json.loads(run("scan", str(FIXTURES), "--format", "json").output)
        assert [r["name"] for r in payload["repositories"]] == [r.name for r in estate.repos]
        assert payload == scan_to_dict(estate)

    def test_a_custom_support_table_changes_the_verdict(self, run, tmp_path):
        table = write(
            tmp_path,
            "table.yaml",
            'as_of: 2020-01-01\nruntimes:\n  - runtime: dotnet\n    version: "6.0"\n'
            "    end_of_support: 2024-11-12\n    source: https://example.invalid\n",
        )
        payload = json.loads(
            run("scan", str(FIXTURES), "--format", "json", "--support-table", str(table)).output
        )
        reporting = next(r for r in payload["repositories"] if r["name"] == "reporting-tool")
        assert reporting["runtime"]["support"] == "supported"


class TestScoreCommand:
    def test_text_output_names_the_unscored_dimensions(self, run):
        output = run("score", str(FIXTURES)).output
        assert "READINESS RUBRIC" in output
        assert "Data and IP governance constraint: —" in output
        assert "Adoption readiness: —" in output
        assert "WORST LEVEL WITHIN EACH ARCHETYPE" in output

    def test_json_reports_human_dimensions_as_null_never_zero(self, run):
        payload = json.loads(run("score", str(FIXTURES), "--format", "json").output)
        human = [s for s in payload["readiness"]["estate"] if s["assessment"] == "human"]
        assert len(human) == 2
        assert all(entry["level"] is None for entry in human)

    def test_json_refuses_a_composite_score_in_the_payload_itself(self, run):
        payload = json.loads(run("score", str(FIXTURES), "--format", "json").output)
        rubric_block = payload["readiness"]["rubric"]
        assert rubric_block["composite_score"] is None
        assert "refused" in rubric_block["composite_rationale"]

    def test_json_matches_the_library_projection(self, run, estate, rubric):
        payload = json.loads(run("score", str(FIXTURES), "--format", "json").output)
        assert payload["readiness"] == report_to_dict(apply(rubric, estate))

    def test_a_custom_rubric_is_honoured(self, run, tmp_path):
        path = write(
            tmp_path,
            "r.yaml",
            "id: tiny\nversion: 9\nas_of: 2026-08-02\ndimensions:\n"
            "  - id: adoption_readiness\n    title: Adoption\n    scope: estate\n"
            "    assessment: human\n    question: who?\n    human_evidence: [ask]\n"
            "    levels:\n      - {level: 0, name: none, definition: nobody}\n",
        )
        output = run("score", str(FIXTURES), "--rubric", str(path)).output
        assert "tiny v9" in output


class TestRubricCommand:
    def test_text_output_flags_the_dimensions_with_no_machine_signal(self, run):
        output = run("rubric").output
        assert output.count("NO MACHINE SIGNAL") == 2
        assert "Requires human assessment:" in output

    def test_text_output_lists_every_level_of_every_dimension(self, run, rubric):
        output = run("rubric").output
        for dimension in rubric.dimensions:
            for level in dimension.levels:
                assert f"L{level.level} {level.name}:" in output

    def test_json_output(self, run, rubric):
        payload = json.loads(run("rubric", "--format", "json").output)
        assert payload["id"] == rubric.id
        assert len(payload["dimensions"]) == len(rubric.dimensions)
        human = [d for d in payload["dimensions"] if d["assessment"] == "human"]
        assert all(d["machine_evidence"] == [] for d in human)


class TestErrors:
    def test_a_missing_root_is_a_usage_error(self, run):
        result = run("scan", "/nonexistent/path", expect_success=False)
        assert result.exit_code == 2

    def test_a_malformed_rubric_is_reported_without_a_traceback(self, run, tmp_path):
        path = write(tmp_path, "r.yaml", "id: t\nversion: 1\nas_of: 2026-08-02\ndimensions: []\n")
        result = run("score", str(FIXTURES), "--rubric", str(path), expect_success=False)
        assert result.exit_code != 0
        assert "declares no dimensions" in str(result.exception)

    def test_help_is_available(self, run):
        assert "brownfield-scan" in run("--help").output or "Usage" in run("--help").output
