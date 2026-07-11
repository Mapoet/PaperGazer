"""Distribution metadata and package discovery regression tests."""

import tomllib
from pathlib import Path

from setuptools import find_packages

ROOT = Path(__file__).resolve().parents[2]


def test_all_runtime_packages_are_discovered() -> None:
    packages = set(find_packages(where=ROOT, include=["papergazer*"]))

    assert {
        "papergazer.analytics",
        "papergazer.core",
        "papergazer.sources",
        "papergazer.store",
        "papergazer.utils",
    } <= packages


def test_pyproject_uses_recursive_package_discovery() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools = metadata["tool"]["setuptools"]
    packages = setuptools["packages"]

    assert isinstance(packages, dict)
    assert "find" in packages
    assert packages["find"]["include"] == ["papergazer*"]


def test_imported_lxml_is_a_runtime_dependency() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert any(item.startswith("lxml") for item in metadata["project"]["dependencies"])
