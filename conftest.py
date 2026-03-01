"""Pytest configuration with Sybil for doc testing."""

import pytest
from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply beartype to test functions."""
    import beartype

    for item in items:
        if hasattr(item, "obj") and callable(item.obj):
            item.obj = beartype.beartype(item.obj)


pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()],
    pattern="*.rst",
).pytest()
