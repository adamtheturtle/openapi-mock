"""Pytest configuration with Sybil for doc testing."""

from collections.abc import Callable
from pathlib import Path

import pytest
from sybil import Sybil
from sybil.integration.pytest import pytest_integration as _pytest_integration
from sybil.parsers.codeblock import PythonCodeBlockParser

pytest_collect_file: Callable[[Path, pytest.Collector], pytest.File | None] = (
    _pytest_integration(
        Sybil(
            parsers=[PythonCodeBlockParser()],
            pattern="*.rst",
        )
    )
)
