"""The tables that say what a stack looks like on disk.

Kept apart from the code that uses them so that adding a stack is a data change
in one place rather than an edit spread across detection, fact-gathering and
rendering. Every entry here is a convention, and conventions are exactly the
thing a brownfield estate does not reliably follow -- which is why the scanner
reports what it matched, not just that it matched something.
"""

from __future__ import annotations

from dataclasses import dataclass

# Directories never descended into. Vendored dependencies and build output would
# otherwise dominate every file count in the report.
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "vendor",
        "target",
        "build",
        "dist",
        "out",
        "bin",
        "obj",
        "__pycache__",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".gradle",
        ".idea",
        ".vscode",
        "site-packages",
    }
)


@dataclass(frozen=True)
class Ecosystem:
    """One language/build-system pairing and how to recognise its artefacts."""

    id: str
    language: str
    build_system: str
    # Root files whose presence selects this ecosystem, in priority order.
    manifests: tuple[str, ...]
    # Lockfile names, in the order they should be reported if several exist.
    lockfiles: tuple[str, ...]
    # False where the ecosystem has no lockfile concept at all. Reporting
    # "no lockfile" for Maven would be scoring it against a mechanism it does
    # not have; Maven pins per dependency instead.
    lockfile_applicable: bool
    source_globs: tuple[str, ...]
    test_globs: tuple[str, ...]
    # Dependency name -> framework family. First match in declaration order of
    # this table wins, so put the more specific marker first.
    frameworks: tuple[tuple[str, str], ...]


ECOSYSTEMS: tuple[Ecosystem, ...] = (
    Ecosystem(
        id="maven",
        language="java",
        build_system="maven",
        manifests=("pom.xml",),
        lockfiles=(),
        lockfile_applicable=False,
        source_globs=("**/*.java", "**/*.kt"),
        test_globs=("src/test/**/*.java", "src/test/**/*.kt"),
        frameworks=(
            ("spring-boot", "spring-boot"),
            ("quarkus", "quarkus"),
            ("micronaut", "micronaut"),
            ("jakarta.", "jakarta-ee"),
            ("javax.servlet", "java-ee"),
        ),
    ),
    Ecosystem(
        id="gradle",
        language="java",
        build_system="gradle",
        manifests=("build.gradle", "build.gradle.kts"),
        lockfiles=("gradle.lockfile",),
        lockfile_applicable=True,
        source_globs=("**/*.java", "**/*.kt"),
        test_globs=("src/test/**/*.java", "src/test/**/*.kt"),
        frameworks=(
            ("spring-boot", "spring-boot"),
            ("quarkus", "quarkus"),
            ("micronaut", "micronaut"),
        ),
    ),
    Ecosystem(
        id="python-pyproject",
        language="python",
        build_system="pyproject",
        manifests=("pyproject.toml",),
        lockfiles=("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"),
        lockfile_applicable=True,
        source_globs=("**/*.py",),
        test_globs=("**/test_*.py", "**/*_test.py"),
        frameworks=(
            ("fastapi", "fastapi"),
            ("django", "django"),
            ("flask", "flask"),
            ("pyspark", "pyspark"),
            ("airflow", "airflow"),
        ),
    ),
    Ecosystem(
        id="python-requirements",
        language="python",
        build_system="pip-requirements",
        manifests=("requirements.txt", "setup.py", "setup.cfg"),
        lockfiles=("requirements.lock", "Pipfile.lock"),
        lockfile_applicable=True,
        source_globs=("**/*.py",),
        test_globs=("**/test_*.py", "**/*_test.py"),
        frameworks=(
            ("fastapi", "fastapi"),
            ("django", "django"),
            ("flask", "flask"),
            ("pyspark", "pyspark"),
            ("airflow", "airflow"),
        ),
    ),
    Ecosystem(
        id="node",
        language="javascript",
        build_system="npm",
        manifests=("package.json",),
        lockfiles=("package-lock.json", "pnpm-lock.yaml", "yarn.lock"),
        lockfile_applicable=True,
        source_globs=("**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"),
        test_globs=(
            "**/*.test.js",
            "**/*.test.jsx",
            "**/*.test.ts",
            "**/*.test.tsx",
            "**/*.spec.js",
            "**/*.spec.ts",
            "**/__tests__/**/*.js",
            "**/__tests__/**/*.ts",
        ),
        frameworks=(
            ("@nestjs/core", "nestjs"),
            ("next", "nextjs"),
            ("react", "react"),
            ("vue", "vue"),
            ("express", "express"),
        ),
    ),
    Ecosystem(
        id="go",
        language="go",
        build_system="go-modules",
        manifests=("go.mod",),
        lockfiles=("go.sum",),
        lockfile_applicable=True,
        source_globs=("**/*.go",),
        test_globs=("**/*_test.go",),
        frameworks=(
            ("github.com/gin-gonic/gin", "gin"),
            ("github.com/labstack/echo", "echo"),
            ("github.com/gofiber/fiber", "fiber"),
        ),
    ),
    Ecosystem(
        id="dotnet",
        language="dotnet",
        build_system="msbuild",
        manifests=("*.sln", "*.csproj", "*.fsproj"),
        lockfiles=("packages.lock.json",),
        lockfile_applicable=True,
        source_globs=("**/*.cs", "**/*.fs"),
        test_globs=("**/*Test.cs", "**/*Tests.cs", "**/*Test.fs"),
        frameworks=(
            ("Microsoft.NET.Sdk.Web", "aspnet-core"),
            ("Microsoft.AspNetCore", "aspnet-core"),
        ),
    ),
    Ecosystem(
        id="ruby",
        language="ruby",
        build_system="bundler",
        manifests=("Gemfile",),
        lockfiles=("Gemfile.lock",),
        lockfile_applicable=True,
        source_globs=("**/*.rb",),
        test_globs=("spec/**/*_spec.rb", "test/**/*_test.rb"),
        frameworks=(("rails", "rails"), ("sinatra", "sinatra")),
    ),
    Ecosystem(
        id="php",
        language="php",
        build_system="composer",
        manifests=("composer.json",),
        lockfiles=("composer.lock",),
        lockfile_applicable=True,
        source_globs=("**/*.php",),
        test_globs=("tests/**/*Test.php",),
        frameworks=(("laravel/framework", "laravel"), ("symfony/", "symfony")),
    ),
)

ECOSYSTEMS_BY_ID = {eco.id: eco for eco in ECOSYSTEMS}

# Container build definitions. Their presence is a reproducibility signal: it
# says someone has already written down the environment the build needs.
CONTAINER_BUILD_FILES: tuple[str, ...] = (
    "Dockerfile",
    "Containerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yaml",
    ".devcontainer/devcontainer.json",
)

# CI configuration, by the file or directory that identifies the system.
CI_MARKERS: tuple[tuple[str, str], ...] = (
    (".github/workflows", "github-actions"),
    (".gitlab-ci.yml", "gitlab-ci"),
    ("Jenkinsfile", "jenkins"),
    ("azure-pipelines.yml", "azure-pipelines"),
    (".circleci/config.yml", "circleci"),
    ("bitbucket-pipelines.yml", "bitbucket-pipelines"),
    (".drone.yml", "drone"),
)

# Static analysis and dependency scanning configuration. Detected by filename
# only -- whether the tool runs, and whether anyone reads its output, is not
# something a filename can tell you.
ANALYSIS_MARKERS: tuple[tuple[str, str], ...] = (
    (".ruff.toml", "ruff"),
    ("ruff.toml", "ruff"),
    (".flake8", "flake8"),
    (".pylintrc", "pylint"),
    ("mypy.ini", "mypy"),
    (".eslintrc", "eslint"),
    (".eslintrc.json", "eslint"),
    ("eslint.config.js", "eslint"),
    ("sonar-project.properties", "sonarqube"),
    ("checkstyle.xml", "checkstyle"),
    ("spotbugs-exclude.xml", "spotbugs"),
    (".semgrep.yml", "semgrep"),
    (".pre-commit-config.yaml", "pre-commit"),
    (".trivyignore", "trivy"),
    ("dependency-check.properties", "owasp-dependency-check"),
    (".github/dependabot.yml", "dependabot"),
    ("renovate.json", "renovate"),
)

# Coverage instrumentation, by the string that declares it and the file it is
# declared in. Configuration only: it says a coverage number could be produced,
# never that one is, and never what it would be.
COVERAGE_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("pyproject.toml", "--cov", "pytest-cov"),
    ("pyproject.toml", "[tool.coverage", "coverage.py"),
    ("setup.cfg", "--cov", "pytest-cov"),
    ("tox.ini", "--cov", "pytest-cov"),
    ("pytest.ini", "--cov", "pytest-cov"),
    (".coveragerc", "", "coverage.py"),
    ("pom.xml", "jacoco", "jacoco"),
    ("build.gradle", "jacoco", "jacoco"),
    ("build.gradle.kts", "jacoco", "jacoco"),
    ("package.json", "collectCoverage", "jest"),
    ("package.json", "nyc", "nyc"),
    (".nycrc", "", "nyc"),
    ("jest.config.js", "coverage", "jest"),
)
