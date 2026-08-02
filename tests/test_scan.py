"""Estate walking, grouping, and the arithmetic of concentration."""

from __future__ import annotations

import pytest

from brownfield_readiness.errors import ScanError
from brownfield_readiness.model import ArchetypeKey, Concentration
from brownfield_readiness.scan import group_by_archetype, scan_estate, scan_repository

from .conftest import FIXTURES, write


class TestWalking:
    def test_a_directory_without_a_manifest_is_skipped_with_a_reason(self, estate):
        assert estate.skipped == (
            ("platform-docs", "no recognised build manifest at the repository root"),
        )

    def test_dotfiles_are_not_treated_as_repositories(self, tmp_path, support_table):
        write(tmp_path, ".github/workflows/ci.yml", "jobs: {}\n")
        write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
        result = scan_estate(tmp_path, support_table)
        assert [repo.name for repo in result.repos] == ["svc"]
        assert result.skipped == ()

    def test_files_at_the_root_are_ignored(self, tmp_path, support_table):
        write(tmp_path, "README.md", "an estate")
        write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
        assert len(scan_estate(tmp_path, support_table).repos) == 1

    @pytest.mark.parametrize(
        ("setup", "match"),
        [
            (lambda p: p / "absent", "does not exist"),
            (lambda p: write(p, "a-file.txt", "x"), "is not a directory"),
        ],
    )
    def test_bad_roots_are_rejected(self, tmp_path, support_table, setup, match: str):
        with pytest.raises(ScanError, match=match):
            scan_estate(setup(tmp_path), support_table)

    def test_an_empty_directory_is_an_error_not_an_empty_report(self, tmp_path, support_table):
        with pytest.raises(ScanError, match="no subdirectories to scan"):
            scan_estate(tmp_path, support_table)

    def test_the_support_table_date_travels_with_the_result(self, estate, support_table):
        assert estate.support_table_as_of == support_table.as_of.isoformat()

    def test_the_default_support_table_is_used_when_none_is_passed(self, tmp_path):
        write(tmp_path, "svc/go.mod", "module example.com/svc\n\ngo 1.22\n")
        assert scan_estate(tmp_path).support_table_as_of == "2026-08-02"


class TestGrouping:
    def test_largest_archetype_first_then_alphabetical(self, estate):
        labels = [archetype.label for archetype in estate.archetypes]
        assert labels[0] == "java / maven / spring-boot"
        assert labels == sorted(
            labels,
            key=lambda label: (
                -len(next(a for a in estate.archetypes if a.label == label).repos),
                label,
            ),
        )

    def test_repositories_within_an_archetype_are_sorted_by_name(self, estate):
        for archetype in estate.archetypes:
            names = [repo.name for repo in archetype.repos]
            assert names == sorted(names)

    def test_grouping_is_stable_across_input_order(self, estate):
        forward = group_by_archetype(estate.repos)
        reverse = group_by_archetype(tuple(reversed(estate.repos)))
        assert [a.key for a in forward] == [a.key for a in reverse]
        assert [[r.name for r in a.repos] for a in forward] == [
            [r.name for r in a.repos] for a in reverse
        ]

    def test_a_scan_of_the_same_tree_twice_is_identical(self, support_table):
        first = scan_estate(FIXTURES, support_table)
        second = scan_estate(FIXTURES, support_table)
        assert first == second

    def test_empty_input(self):
        assert group_by_archetype(()) == ()


class TestConcentration:
    def test_the_fixture_estate_barely_concentrates(self, estate):
        concentration = estate.concentration
        assert (concentration.repositories, concentration.archetypes) == (8, 7)
        assert concentration.reuse_factor == pytest.approx(0.125)
        assert concentration.mean_repos_per_archetype == pytest.approx(8 / 7)

    @pytest.mark.parametrize(
        ("repos", "archetypes", "reuse"),
        [(20, 4, 0.8), (20, 20, 0.0), (1, 1, 0.0), (10, 5, 0.5)],
    )
    def test_reuse_factor_is_one_minus_archetypes_over_repositories(
        self, repos: int, archetypes: int, reuse: float
    ):
        assert Concentration(repos, archetypes).reuse_factor == pytest.approx(reuse)

    def test_an_empty_estate_has_no_reuse_factor_rather_than_zero(self):
        empty = Concentration(repositories=0, archetypes=0)
        assert empty.reuse_factor is None
        assert empty.mean_repos_per_archetype is None


class TestArchetypeKey:
    def test_label_names_the_absence_of_a_framework(self):
        assert (
            ArchetypeKey("go", "go-modules", None).label
            == "go / go-modules / no framework detected"
        )

    def test_sort_key_puts_a_missing_framework_last(self):
        assert (
            ArchetypeKey("java", "maven", None).sort_key()
            > ArchetypeKey("java", "maven", "spring-boot").sort_key()
        )


def test_scan_repository_of_an_unrecognised_directory(tmp_path, support_table):
    facts = scan_repository(tmp_path, support_table)
    assert facts.archetype.language == "unknown"
    assert facts.build.manifests == ()
    assert facts.tests.test_command is None
