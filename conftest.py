"""Pytest configuration with Sybil for doc testing."""

import pytest
from beartype import beartype
from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply the beartype decorator to all collected test functions."""
    for item in items:
        if isinstance(item, pytest.Function):
            item.obj = beartype(obj=item.obj)


pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()],
    pattern="*.rst",
).pytest()
