"""Shared fixtures.

`estate` is the committed fixture tree, not a temporary one. Every table in the
README comes from scanning it, so a test that changes its shape changes the
README, which is the point: the documentation and the test suite are asserting
against the same tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brownfield_readiness.model import ScanResult
from brownfield_readiness.rubric import Rubric, load_rubric
from brownfield_readiness.runtimes import SupportTable, load_support_table
from brownfield_readiness.scan import scan_estate

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures"


@pytest.fixture(scope="session")
def support_table() -> SupportTable:
    return load_support_table()


@pytest.fixture(scope="session")
def rubric() -> Rubric:
    return load_rubric()


@pytest.fixture(scope="session")
def estate(support_table: SupportTable) -> ScanResult:
    return scan_estate(FIXTURES, support_table)


@pytest.fixture
def repo_by_name(estate: ScanResult):
    index = {repo.name: repo for repo in estate.repos}

    def _get(name: str):
        return index[name]

    return _get


def write(root: Path, relative: str, content: str = "") -> Path:
    """Create a file under `root`, making parent directories as needed."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
