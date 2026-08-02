"""The support table, its provenance, and the reproducibility of the comparison."""

from __future__ import annotations

from datetime import date

import pytest

from brownfield_readiness.ecosystems import ECOSYSTEMS_BY_ID
from brownfield_readiness.errors import SupportTableError
from brownfield_readiness.model import Support
from brownfield_readiness.runtimes import (
    SupportTable,
    declared_runtime,
    default_support_table,
    load_support_table,
    runtime_facts,
)

from .conftest import FIXTURES, write

_MINIMAL = """
as_of: 2026-08-02
runtimes:
  - runtime: python
    version: "3.9"
    end_of_support: 2025-10-31
    source: https://example.invalid/versions
"""


class TestProvenanceIsEnforced:
    """The claim this repository would most deserve to be disbelieved for.

    Every end-of-support date printed by the scanner is transcribed from
    somewhere. If an entry could ship without a URL and a date, the tool would be
    asserting a fact about a customer's estate with no way for anyone to check
    it. These run as their own CI job for that reason.
    """

    def test_every_shipped_entry_carries_a_source_url(self, support_table: SupportTable):
        for entry in support_table.entries:
            assert entry.source.startswith("https://"), entry

    def test_the_shipped_table_is_dated(self, support_table: SupportTable):
        assert isinstance(support_table.as_of, date)

    def test_the_filename_matches_the_as_of_month(self, support_table: SupportTable):
        name = default_support_table().name
        assert support_table.as_of.strftime("%Y-%m") in name

    def test_java_entries_name_the_distribution_they_apply_to(self, support_table: SupportTable):
        """Java has no single end-of-support date; an unqualified one would mislead."""
        java = [entry for entry in support_table.entries if entry.runtime == "java"]
        assert java
        for entry in java:
            assert entry.note and "Temurin" in entry.note

    def test_an_entry_without_a_source_is_rejected(self, tmp_path):
        path = write(
            tmp_path,
            "table.yaml",
            'as_of: 2026-08-02\nruntimes:\n  - runtime: go\n    version: "1.22"\n'
            "    end_of_support: 2026-01-01\n",
        )
        with pytest.raises(SupportTableError, match="missing: source"):
            load_support_table(path)

    def test_a_source_that_is_not_a_url_is_rejected(self, tmp_path):
        path = write(
            tmp_path,
            "table.yaml",
            'as_of: 2026-08-02\nruntimes:\n  - runtime: go\n    version: "1.22"\n'
            "    end_of_support: 2026-01-01\n    source: I asked a colleague\n",
        )
        with pytest.raises(SupportTableError, match="must be a URL"):
            load_support_table(path)


class TestTableLoading:
    @pytest.mark.parametrize(
        ("content", "match"),
        [
            ("[]", "must be a mapping"),
            ("runtimes: []", "`as_of` date"),
            ("as_of: 2026-08-02\n", "non-empty `runtimes`"),
            ("as_of: 2026-08-02\nruntimes: []\n", "non-empty `runtimes`"),
            ("as_of: 2026-08-02\nruntimes:\n  - just a string\n", "must be a mapping"),
            ("as_of: not-a-date\nruntimes: []\n", "`as_of` date"),
        ],
    )
    def test_malformed_tables_are_rejected(self, tmp_path, content: str, match: str):
        path = write(tmp_path, "table.yaml", content)
        with pytest.raises(SupportTableError, match=match):
            load_support_table(path)

    def test_a_non_date_end_of_support_is_rejected(self, tmp_path):
        path = write(
            tmp_path,
            "table.yaml",
            'as_of: 2026-08-02\nruntimes:\n  - runtime: go\n    version: "1.22"\n'
            "    end_of_support: soon\n    source: https://example.invalid\n",
        )
        with pytest.raises(SupportTableError, match="must be a date"):
            load_support_table(path)

    def test_unreadable_file(self, tmp_path):
        with pytest.raises(SupportTableError, match="cannot read"):
            load_support_table(tmp_path / "absent.yaml")

    def test_invalid_yaml(self, tmp_path):
        path = write(tmp_path, "table.yaml", "as_of: [unclosed\n")
        with pytest.raises(SupportTableError, match="not valid YAML"):
            load_support_table(path)


class TestDeclaredVersions:
    @pytest.mark.parametrize(
        ("repo", "eco_id", "expected"),
        [
            ("orders-api", "python-pyproject", ("python", "3.12")),
            ("invoicing-api", "python-requirements", ("python", "3.9")),
            ("customer-portal", "maven", ("java", "17")),
            ("legacy-batch", "maven", ("java", "8")),
            ("web-frontend", "node", ("node", "18")),
            ("notify-worker", "go", ("go", "1.22")),
            ("reporting-tool", "dotnet", ("dotnet", "6.0")),
        ],
    )
    def test_fixture_runtimes(self, repo: str, eco_id: str, expected: tuple[str, str]):
        found = declared_runtime(FIXTURES / repo, ECOSYSTEMS_BY_ID[eco_id])
        assert (found[0], found[1]) == expected

    def test_maven_pre_nine_spelling_is_normalised(self, tmp_path):
        write(
            tmp_path,
            "pom.xml",
            "<project><properties><maven.compiler.source>1.8"
            "</maven.compiler.source></properties></project>",
        )
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["maven"])[1] == "8"

    def test_nvmrc_is_read_when_engines_is_absent(self, tmp_path):
        write(tmp_path, "package.json", '{"name": "x"}')
        write(tmp_path, ".nvmrc", "v20.11.0\n")
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["node"]) == ("node", "20", ".nvmrc")

    def test_dockerfile_is_the_last_resort_for_python(self, tmp_path):
        write(tmp_path, "requirements.txt", "requests==2.32.3\n")
        write(tmp_path, "Dockerfile", "FROM python:3.11-slim\n")
        found = declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["python-requirements"])
        assert found == ("python", "3.11", "Dockerfile base image")

    def test_gradle_java_version(self, tmp_path):
        write(tmp_path, "build.gradle", "java { sourceCompatibility = '21' }\n")
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["gradle"]) == (
            "java",
            "21",
            "build.gradle",
        )

    def test_broken_pyproject_falls_through(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[project\n")
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["python-pyproject"]) is None

    def test_broken_package_json_falls_through(self, tmp_path):
        write(tmp_path, "package.json", "{broken")
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["node"]) is None

    def test_ecosystems_without_a_declared_runtime_concept(self, tmp_path):
        assert declared_runtime(tmp_path, ECOSYSTEMS_BY_ID["ruby"]) is None
        assert declared_runtime(tmp_path, None) is None


class TestSupportVerdicts:
    def test_comparison_is_against_the_table_date_not_today(self, tmp_path):
        """A scan is reproducible; the verdict moves when the table is updated.

        The same repository is end-of-support against one table and supported
        against another that differs only in its as-of date. Nothing here reads
        a clock.
        """
        repo = tmp_path / "repo"
        write(repo, "requirements.txt", "requests==2.32.3\n")
        write(repo, ".python-version", "3.9\n")

        current = load_support_table(write(tmp_path, "now.yaml", _MINIMAL))
        earlier = load_support_table(
            write(tmp_path, "then.yaml", _MINIMAL.replace("as_of: 2026-08-02", "as_of: 2024-01-01"))
        )
        eco = ECOSYSTEMS_BY_ID["python-requirements"]
        assert runtime_facts(repo, eco, current).support is Support.END_OF_SUPPORT
        assert runtime_facts(repo, eco, earlier).support is Support.SUPPORTED

    def test_a_runtime_absent_from_the_table_is_unknown_not_supported(
        self, support_table: SupportTable
    ):
        facts = runtime_facts(FIXTURES / "notify-worker", ECOSYSTEMS_BY_ID["go"], support_table)
        assert facts.support is Support.UNKNOWN
        assert facts.version == "1.22"
        assert facts.end_of_support is None

    def test_nothing_declared_is_reported_distinctly(self, tmp_path, support_table):
        write(tmp_path, "Gemfile", "gem 'rails', '7.1.3'\n")
        facts = runtime_facts(tmp_path, ECOSYSTEMS_BY_ID["ruby"], support_table)
        assert facts.support is Support.NOT_DECLARED
        assert facts.name is None

    def test_end_of_support_carries_the_date_and_the_source(self, support_table):
        facts = runtime_facts(
            FIXTURES / "reporting-tool", ECOSYSTEMS_BY_ID["dotnet"], support_table
        )
        assert facts.support is Support.END_OF_SUPPORT
        assert facts.end_of_support == "2024-11-12"
        assert facts.source.startswith("https://")
