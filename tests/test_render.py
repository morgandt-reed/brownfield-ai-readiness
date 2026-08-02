"""Rendering, the JSON projection, and the process-level entry point."""

from __future__ import annotations

import json

import pytest

from brownfield_readiness import cli
from brownfield_readiness.errors import RubricError, SupportTableError
from brownfield_readiness.render import (
    _columns,
    render_archetype_map,
    render_fact_sheets,
    render_rubric,
    render_scan,
)
from brownfield_readiness.resources import find_upward, locate
from brownfield_readiness.rubric import apply, load_rubric
from brownfield_readiness.scan import scan_estate
from brownfield_readiness.serialize import report_to_dict, scan_to_dict

from .conftest import write


class TestTables:
    def test_empty_input(self):
        assert _columns([]) == []

    def test_columns_are_padded_and_right_trimmed(self):
        assert _columns([("a", "bb"), ("ccc", "d")]) == ["a    bb", "ccc  d"]


class TestArchetypeMap:
    def test_it_states_what_the_reuse_factor_is_not(self, estate):
        text = render_archetype_map(estate)
        assert "Reuse factor: 0.12" in text
        assert "does not measure how much of" in text

    def test_skipped_directories_are_named(self, estate):
        assert "platform-docs" in render_archetype_map(estate)

    def test_a_single_repository_estate_reads_grammatically(self, tmp_path, support_table):
        write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
        text = render_fact_sheets(scan_estate(tmp_path, support_table))
        assert "(1 repository)" in text
        assert "repositories)" not in text


class TestFactSheets:
    def test_maven_lockfile_line_says_inapplicable_not_missing(self, estate):
        assert "n/a — this build system has no lockfile" in render_fact_sheets(estate)

    def test_an_uninferable_test_command_says_so(self, estate):
        assert "could not be inferred" in render_fact_sheets(estate)

    def test_a_repository_with_no_declared_runtime(self, tmp_path, support_table):
        write(tmp_path, "svc/Gemfile", "gem 'rails', '7.1.3'\n")
        text = render_fact_sheets(scan_estate(tmp_path, support_table))
        assert "not declared in the repository" in text

    def test_a_repository_with_no_dependencies_declared(self, tmp_path, support_table):
        write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
        text = render_fact_sheets(scan_estate(tmp_path, support_table))
        assert "no direct dependencies declared" in text


class TestRubricRendering:
    def test_unscored_dimensions_render_as_a_dash_not_a_zero(self, estate, rubric):
        text = render_rubric(apply(rubric, estate), estate)
        assert "Adoption readiness: —" in text
        assert "Adoption readiness: L0" not in text

    def test_the_refusal_to_total_is_printed_not_merely_implied(self, estate, rubric):
        text = render_rubric(apply(rubric, estate), estate)
        assert "no composite score, on purpose" in text

    def test_worst_level_within_an_archetype_picks_the_binding_repository(self, estate, rubric):
        """Two Spring Boot repositories, one at L3 and one at L1. The row shows L1."""
        text = render_rubric(apply(rubric, estate), estate)
        row = next(
            line for line in text.splitlines() if line.strip().startswith("java/maven/spring-boot")
        )
        assert "L1 manifest-only" in row

    def test_an_all_human_rubric_renders_dashes_in_every_repository_cell(self, estate, tmp_path):
        path = write(
            tmp_path,
            "r.yaml",
            "id: t\nversion: 1\nas_of: 2026-08-02\ndimensions:\n"
            "  - id: code_quality\n    title: Code quality\n    scope: repository\n"
            "    assessment: human\n    question: is it good?\n    human_evidence: [read it]\n"
            "    levels:\n      - {level: 0, name: unknown, definition: nobody looked}\n",
        )
        text = render_rubric(apply(load_rubric(path), estate), estate)
        archetype_row = next(
            line for line in text.splitlines() if "python/pyproject/fastapi" in line
        )
        assert archetype_row.strip().endswith("—")

    def test_a_report_with_no_repositories_still_renders(self, tmp_path, rubric, support_table):
        estate_root = tmp_path / "estate"
        write(estate_root, "notes/README.md", "no manifests here")
        result = scan_estate(estate_root, support_table)
        text = render_rubric(apply(rubric, result), result)
        assert "PER-REPOSITORY DIMENSIONS" not in text
        assert "no repositories were scanned" in text


def test_render_scan_always_states_what_it_did_not_do(estate):
    text = render_scan(estate)
    assert text.endswith("\n")
    assert "It did not run a build, run a test" in text
    assert f"table dated {estate.support_table_as_of}" in text


class TestSerialisation:
    def test_the_json_projection_round_trips_through_json(self, estate, rubric):
        payload = scan_to_dict(estate) | {"readiness": report_to_dict(apply(rubric, estate))}
        assert json.loads(json.dumps(payload)) == payload

    def test_no_absolute_path_leaks_into_the_archetype_summary(self, estate):
        payload = scan_to_dict(estate)
        assert all("/" not in name for a in payload["archetypes"] for name in a["repositories"])


class TestResourceLocation:
    def test_find_upward_reports_the_flag_to_pass_instead(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="--support-table"):
            find_upward("data", "runtime-support-*.yaml", "--support-table", tmp_path / "deep")

    def test_locate_wraps_the_failure_in_the_package_error_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "brownfield_readiness.resources.find_upward",
            lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("nope")),
        )
        with pytest.raises(SupportTableError, match="nope"):
            locate("data", "*.yaml", "--support-table", SupportTableError)


class TestProcessEntryPoint:
    def test_a_successful_run_does_not_exit_non_zero(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["brownfield-scan", "rubric"])
        cli.run()
        assert "brownfield-agentic-readiness" in capsys.readouterr().out

    def test_a_package_error_is_one_line_on_stderr_with_exit_two(
        self, monkeypatch, capsys, tmp_path
    ):
        path = write(tmp_path, "r.yaml", "id: t\nversion: 1\nas_of: 2026-08-02\ndimensions: []\n")
        monkeypatch.setattr("sys.argv", ["brownfield-scan", "rubric", "--rubric", str(path)])
        with pytest.raises(SystemExit) as exit_info:
            cli.run()
        assert exit_info.value.code == 2
        captured = capsys.readouterr()
        assert captured.err.startswith("brownfield-scan: ")
        assert "Traceback" not in captured.err

    def test_a_usage_error_keeps_click_s_exit_code(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["brownfield-scan", "scan", "/nonexistent"])
        with pytest.raises(SystemExit) as exit_info:
            cli.run()
        assert exit_info.value.code == 2

    def test_an_interrupt_exits_one_hundred_and_thirty(self, monkeypatch):
        import click

        def abort(*args, **kwargs):
            raise click.exceptions.Abort()

        monkeypatch.setattr(cli.main, "main", abort)
        with pytest.raises(SystemExit) as exit_info:
            cli.run()
        assert exit_info.value.code == 130

    def test_an_unexpected_error_is_not_swallowed(self, monkeypatch):
        """A bug should crash with a traceback rather than be reported as a user error."""

        def boom(*args, **kwargs):
            raise RuntimeError("a bug")

        monkeypatch.setattr(cli.main, "main", boom)
        with pytest.raises(RuntimeError, match="a bug"):
            cli.run()


def test_error_types_share_a_base_the_cli_can_catch():
    assert issubclass(RubricError, cli.BrownfieldError)
    assert issubclass(SupportTableError, cli.BrownfieldError)
