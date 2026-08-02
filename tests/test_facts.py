"""Test presence, CI presence, and the difference between them and reality."""

from __future__ import annotations

import pytest

from brownfield_readiness.ecosystems import ECOSYSTEMS_BY_ID
from brownfield_readiness.facts import (
    _glob_regex,
    collect_build_facts,
    collect_ci_facts,
    collect_test_facts,
    container_build_files,
    count_source_and_test_files,
    coverage_config,
    infer_test_command,
    iter_files,
)

from .conftest import FIXTURES, write


class TestGlobMatching:
    @pytest.mark.parametrize(
        ("pattern", "path", "expected"),
        [
            ("**/*.py", "a.py", True),
            ("**/*.py", "src/pkg/a.py", True),
            ("**/*.py", "a.pyc", False),
            ("**/test_*.py", "tests/test_a.py", True),
            ("**/test_*.py", "tests/a.py", False),
            ("src/test/**/*.java", "src/test/java/A.java", True),
            ("src/test/**/*.java", "src/main/java/A.java", False),
            ("src/test/**/*.java", "src/test/A.java", True),
            ("**/__tests__/**/*.js", "app/__tests__/deep/a.js", True),
            ("*.csproj", "App.csproj", True),
            ("*.csproj", "sub/App.csproj", False),
        ],
    )
    def test_patterns(self, pattern: str, path: str, expected: bool):
        assert bool(_glob_regex(pattern).match(path)) is expected

    def test_single_star_does_not_cross_a_separator(self):
        """The reason `fnmatch` is not used: it would match this."""
        assert _glob_regex("*.py").match("src/a.py") is None


class TestFileWalking:
    def test_ignored_directories_are_not_descended(self, tmp_path):
        write(tmp_path, "app.py")
        write(tmp_path, "node_modules/left-pad/index.js")
        write(tmp_path, ".venv/lib/site.py")
        assert [p.name for p in iter_files(tmp_path)] == ["app.py"]

    def test_symlinks_are_skipped(self, tmp_path):
        target = write(tmp_path, "real.py")
        (tmp_path / "link.py").symlink_to(target)
        assert [p.name for p in iter_files(tmp_path)] == ["real.py"]

    def test_unreadable_directory_does_not_abort_the_walk(self, tmp_path):
        write(tmp_path, "app.py")
        locked = tmp_path / "locked"
        locked.mkdir()
        write(tmp_path, "locked/hidden.py")
        locked.chmod(0o000)
        try:
            assert [p.name for p in iter_files(tmp_path)] == ["app.py"]
        finally:
            locked.chmod(0o755)


class TestCounting:
    def test_a_test_file_is_not_also_a_source_file(self):
        source, tests = count_source_and_test_files(
            FIXTURES / "orders-api", ECOSYSTEMS_BY_ID["python-pyproject"]
        )
        assert (source, tests) == (3, 2)

    def test_java_tests_are_found_under_src_test(self):
        source, tests = count_source_and_test_files(
            FIXTURES / "customer-portal", ECOSYSTEMS_BY_ID["maven"]
        )
        assert (source, tests) == (2, 1)

    def test_no_ecosystem_means_no_counts(self, tmp_path):
        assert count_source_and_test_files(tmp_path, None) == (0, 0)

    def test_ratio_is_none_when_there_is_no_source(self, tmp_path):
        facts = collect_test_facts(tmp_path, None)
        assert facts.test_to_source_ratio is None


class TestInferringATestCommand:
    def test_pytest_is_inferred_from_project_configuration(self):
        command, basis = infer_test_command(
            FIXTURES / "orders-api", ECOSYSTEMS_BY_ID["python-pyproject"]
        )
        assert command == "pytest"
        assert "pytest" in basis

    def test_python_without_a_declared_runner_infers_nothing(self):
        assert infer_test_command(
            FIXTURES / "invoicing-api", ECOSYSTEMS_BY_ID["python-requirements"]
        ) == (None, None)

    def test_unittest_is_a_weaker_but_real_signal(self, tmp_path):
        write(tmp_path, "setup.cfg", "[options]\ntest_suite = unittest\n")
        command, basis = infer_test_command(tmp_path, ECOSYSTEMS_BY_ID["python-requirements"])
        assert command == "python -m unittest discover"
        assert "unittest" in basis

    def test_npm_placeholder_script_is_not_a_test_command(self, tmp_path):
        write(
            tmp_path,
            "package.json",
            '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}',
        )
        assert infer_test_command(tmp_path, ECOSYSTEMS_BY_ID["node"]) == (None, None)

    def test_real_npm_script_is_reported_with_the_script_body(self):
        command, basis = infer_test_command(FIXTURES / "web-frontend", ECOSYSTEMS_BY_ID["node"])
        assert command == "npm test"
        assert "jest --collectCoverage" in basis

    def test_broken_package_json_infers_nothing(self, tmp_path):
        write(tmp_path, "package.json", "{broken")
        assert infer_test_command(tmp_path, ECOSYSTEMS_BY_ID["node"]) == (None, None)

    def test_an_inferable_command_is_not_evidence_that_tests_exist(self):
        """The single most important behaviour in this module.

        `legacy-batch` has no tests whatsoever. `mvn -B test` is still a valid
        command because Maven defines a test phase. A tool that reported
        "test command found" as testability would rate this repository as
        having an oracle, which is exactly backwards.
        """
        facts = collect_test_facts(FIXTURES / "legacy-batch", ECOSYSTEMS_BY_ID["maven"])
        assert facts.test_command == "mvn -B test"
        assert "exists whether or not tests do" in facts.test_command_basis
        assert facts.test_files == 0

    @pytest.mark.parametrize(
        ("eco_id", "expected"),
        [
            ("go", "go test ./..."),
            ("dotnet", "dotnet test"),
            ("ruby", "bundle exec rspec"),
            ("php", "vendor/bin/phpunit"),
        ],
    )
    def test_lifecycle_commands(self, tmp_path, eco_id: str, expected: str):
        assert infer_test_command(tmp_path, ECOSYSTEMS_BY_ID[eco_id])[0] == expected

    def test_gradle_prefers_the_wrapper_when_present(self, tmp_path):
        assert infer_test_command(tmp_path, ECOSYSTEMS_BY_ID["gradle"])[0] == "gradle test"
        write(tmp_path, "gradlew", "#!/bin/sh\n")
        assert infer_test_command(tmp_path, ECOSYSTEMS_BY_ID["gradle"])[0] == "./gradlew test"

    def test_no_ecosystem_infers_nothing(self, tmp_path):
        assert infer_test_command(tmp_path, None) == (None, None)


class TestCoverageAndCI:
    def test_coverage_marker_requires_the_needle_to_be_present(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[project]\nname = 'x'\n")
        assert coverage_config(tmp_path) == ()
        write(tmp_path, "pyproject.toml", '[tool.pytest.ini_options]\naddopts = "--cov=x"\n')
        assert coverage_config(tmp_path) == ("pytest-cov",)

    def test_a_bare_marker_file_needs_no_needle(self, tmp_path):
        write(tmp_path, ".coveragerc", "")
        assert coverage_config(tmp_path) == ("coverage.py",)

    def test_github_workflows_directory_needs_a_yaml_file_in_it(self, tmp_path):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        assert collect_ci_facts(tmp_path, collect_test_facts(tmp_path, None)).configs == ()
        write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  build:\n    steps: []\n")
        assert collect_ci_facts(tmp_path, collect_test_facts(tmp_path, None)).configs == (
            "github-actions",
        )

    def test_ci_that_never_mentions_tests_is_reported_as_such(self, tmp_path):
        write(tmp_path, ".gitlab-ci.yml", "build:\n  script: make package\n")
        assert (
            collect_ci_facts(tmp_path, collect_test_facts(tmp_path, None)).references_tests is False
        )

    def test_analysis_tooling_is_detected_by_filename(self):
        facts = collect_ci_facts(
            FIXTURES / "web-frontend",
            collect_test_facts(FIXTURES / "web-frontend", ECOSYSTEMS_BY_ID["node"]),
        )
        assert facts.analysis_tools == ("eslint",)
        assert facts.references_tests is True


class TestBuildFacts:
    def test_manifests_from_every_matching_ecosystem_are_listed(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[project]\nname='x'\ndependencies=[]\n")
        write(tmp_path, "package.json", '{"name": "x"}')
        facts = collect_build_facts(tmp_path, ECOSYSTEMS_BY_ID["python-pyproject"])
        assert facts.manifests == ("pyproject.toml", "package.json")

    def test_maven_reports_lockfiles_as_inapplicable_rather_than_absent(self):
        facts = collect_build_facts(FIXTURES / "customer-portal", ECOSYSTEMS_BY_ID["maven"])
        assert facts.lockfile is None
        assert facts.lockfile_applicable is False

    def test_pinned_fraction_is_none_when_nothing_is_declared(self, tmp_path):
        write(tmp_path, "go.mod", "module example.com/x\n\ngo 1.22\n")
        facts = collect_build_facts(tmp_path, ECOSYSTEMS_BY_ID["go"])
        assert facts.declared_dependencies == 0
        assert facts.pinned_fraction is None

    def test_container_build_files(self):
        assert container_build_files(FIXTURES / "orders-api") == ("Dockerfile",)
        assert container_build_files(FIXTURES / "invoicing-api") == ()

    def test_no_ecosystem_yields_empty_collect_build_facts(self, tmp_path):
        facts = collect_build_facts(tmp_path, None)
        assert facts.manifests == ()
        assert facts.lockfile_applicable is False
