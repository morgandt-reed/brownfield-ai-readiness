"""Archetype detection, and dependency pinning per ecosystem."""

from __future__ import annotations

import pytest

from brownfield_readiness.detect import (
    count_dependencies,
    detect_archetype,
    detect_ecosystem,
    detect_framework,
    matching_ecosystems,
    read_text,
)
from brownfield_readiness.ecosystems import ECOSYSTEMS_BY_ID

from .conftest import FIXTURES, write


@pytest.mark.parametrize(
    ("repo", "language", "build_system", "framework"),
    [
        ("orders-api", "python", "pyproject", "fastapi"),
        ("invoicing-api", "python", "pip-requirements", "fastapi"),
        ("customer-portal", "java", "maven", "spring-boot"),
        ("inventory-api", "java", "maven", "spring-boot"),
        ("legacy-batch", "java", "maven", None),
        ("web-frontend", "javascript", "npm", "react"),
        ("notify-worker", "go", "go-modules", None),
        ("reporting-tool", "dotnet", "msbuild", None),
    ],
)
def test_fixture_archetypes(repo: str, language: str, build_system: str, framework: str | None):
    key = detect_archetype(FIXTURES / repo)
    assert (key.language, key.build_system, key.framework) == (language, build_system, framework)


def test_directory_without_a_manifest_is_not_an_ecosystem():
    assert detect_ecosystem(FIXTURES / "platform-docs") is None


def test_unrecognised_repository_gets_the_unknown_archetype(tmp_path):
    key = detect_archetype(tmp_path)
    assert key.language == "unknown"
    assert key.label == "unknown / unknown / no framework detected"


def test_two_spring_boot_repos_share_an_archetype_key():
    assert detect_archetype(FIXTURES / "customer-portal") == detect_archetype(
        FIXTURES / "inventory-api"
    )


def test_framework_splits_two_maven_repositories_apart():
    """The point of including the framework family in the key.

    `legacy-batch` and `inventory-api` share a language and a build system and
    are not the same onboarding problem.
    """
    assert detect_archetype(FIXTURES / "legacy-batch") != detect_archetype(
        FIXTURES / "inventory-api"
    )


def test_precedence_is_table_order_when_several_manifests_are_present(tmp_path):
    write(tmp_path, "pyproject.toml", "[project]\nname='x'\ndependencies=[]\n")
    write(tmp_path, "package.json", '{"name": "x"}')
    assert [eco.id for eco in matching_ecosystems(tmp_path)] == ["python-pyproject", "node"]
    assert detect_ecosystem(tmp_path).id == "python-pyproject"


def test_read_text_returns_empty_for_a_missing_file(tmp_path):
    assert read_text(tmp_path / "nothing.txt") == ""


class TestPinning:
    def test_pyproject_counts_optional_dependency_groups(self):
        declared, pinned = count_dependencies(
            FIXTURES / "orders-api", ECOSYSTEMS_BY_ID["python-pyproject"]
        )
        assert (declared, pinned) == (6, 6)

    def test_requirements_ranges_are_not_pinned(self):
        declared, pinned = count_dependencies(
            FIXTURES / "invoicing-api", ECOSYSTEMS_BY_ID["python-requirements"]
        )
        assert (declared, pinned) == (4, 0)

    def test_requirements_skips_comments_and_flags(self, tmp_path):
        write(
            tmp_path,
            "requirements.txt",
            "# a comment\n-r other.txt\n\nrequests==2.32.3\nurllib3>=2\n",
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["python-requirements"]) == (2, 1)

    def test_maven_literal_versions_are_pinned(self):
        assert count_dependencies(FIXTURES / "customer-portal", ECOSYSTEMS_BY_ID["maven"]) == (3, 3)

    def test_maven_parent_managed_versions_read_as_unpinned(self):
        """A true statement about the file and a misleading one about the build.

        `inventory-api` inherits versions from a Spring Boot parent POM. The
        scanner sees three dependencies with no `<version>` and reports weak
        pinning. The README says so, because the alternative -- resolving parent
        POMs -- means being a build tool.
        """
        assert count_dependencies(FIXTURES / "inventory-api", ECOSYSTEMS_BY_ID["maven"]) == (4, 1)

    @pytest.mark.parametrize("version", ["${spring.version}", "[1.0,2.0)", "LATEST", "RELEASE"])
    def test_maven_non_literal_versions_are_not_pinned(self, tmp_path, version: str):
        write(
            tmp_path,
            "pom.xml",
            f"<project><dependencies><dependency><groupId>g</groupId>"
            f"<artifactId>a</artifactId><version>{version}</version>"
            f"</dependency></dependencies></project>",
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["maven"]) == (1, 0)

    def test_node_carets_are_not_pinned(self):
        assert count_dependencies(FIXTURES / "web-frontend", ECOSYSTEMS_BY_ID["node"]) == (5, 3)

    def test_go_requires_are_pinned_by_construction(self):
        assert count_dependencies(FIXTURES / "notify-worker", ECOSYSTEMS_BY_ID["go"]) == (2, 2)

    def test_dotnet_package_references(self):
        assert count_dependencies(FIXTURES / "reporting-tool", ECOSYSTEMS_BY_ID["dotnet"]) == (2, 2)

    def test_dotnet_wildcard_version_is_not_pinned(self, tmp_path):
        write(
            tmp_path,
            "App.csproj",
            '<Project><ItemGroup><PackageReference Include="X" Version="1.*" />'
            "</ItemGroup></Project>",
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["dotnet"]) == (1, 0)

    def test_gradle_coordinates(self, tmp_path):
        write(
            tmp_path,
            "build.gradle",
            "dependencies {\n"
            "  implementation 'org.example:lib:1.2.3'\n"
            "  testImplementation 'org.example:test:2.0+'\n"
            "}\n",
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["gradle"]) == (2, 1)

    def test_ruby_gemfile(self, tmp_path):
        write(tmp_path, "Gemfile", "gem 'rails', '7.1.3'\ngem 'puma', '~> 6.0'\ngem 'rake'\n")
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["ruby"]) == (3, 1)

    def test_composer_ignores_the_php_constraint_itself(self, tmp_path):
        write(
            tmp_path,
            "composer.json",
            '{"require": {"php": "^8.2", "monolog/monolog": "3.7.0",'
            ' "symfony/console": "^7.0"}}',
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["php"]) == (2, 1)

    @pytest.mark.parametrize(
        ("manifest", "eco_id"),
        [("package.json", "node"), ("composer.json", "php")],
    )
    def test_malformed_json_yields_no_dependencies(self, tmp_path, manifest: str, eco_id: str):
        write(tmp_path, manifest, "{not json")
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID[eco_id]) == (0, 0)

    def test_malformed_toml_yields_no_dependencies(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[project\n")
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["python-pyproject"]) == (0, 0)

    def test_poetry_style_dependencies_are_counted(self, tmp_path):
        write(
            tmp_path,
            "pyproject.toml",
            '[tool.poetry.dependencies]\npython = "^3.11"\nrequests = "==2.32.3"\nflask = "^3"\n',
        )
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["python-pyproject"]) == (2, 1)


class TestFrameworkDetection:
    def test_node_matches_dependency_names_not_raw_text(self, tmp_path):
        # "express" appears only in a description, so it must not be matched.
        write(
            tmp_path,
            "package.json",
            '{"description": "an express-like service", "dependencies": {"react": "18.0.0"}}',
        )
        assert detect_framework(tmp_path, ECOSYSTEMS_BY_ID["node"]) == "react"

    def test_node_with_broken_manifest_has_no_framework(self, tmp_path):
        write(tmp_path, "package.json", "{oops")
        assert detect_framework(tmp_path, ECOSYSTEMS_BY_ID["node"]) is None

    def test_node_manifest_that_is_not_an_object(self, tmp_path):
        write(tmp_path, "package.json", "[]")
        assert detect_framework(tmp_path, ECOSYSTEMS_BY_ID["node"]) is None
        assert count_dependencies(tmp_path, ECOSYSTEMS_BY_ID["node"]) == (0, 0)

    def test_first_matching_marker_wins(self, tmp_path):
        write(tmp_path, "requirements.txt", "django==5.1\nflask==3.0\n")
        # `django` is declared before `flask` in the ecosystem table.
        assert detect_framework(tmp_path, ECOSYSTEMS_BY_ID["python-requirements"]) == "django"
