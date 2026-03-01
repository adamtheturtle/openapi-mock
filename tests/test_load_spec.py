"""Tests for load_spec."""

import tempfile
from pathlib import Path

import pytest

from openapi_mock import load_spec


def test_load_json() -> None:
    """JSON files are loaded correctly."""
    spec = {"openapi": "3.0.0", "paths": {}}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        Path(f.name).write_text('{"openapi": "3.0.0", "paths": {}}')
        result = load_spec(f.name)
    assert result == spec


def test_load_yaml() -> None:
    """YAML files are loaded correctly."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        Path(f.name).write_text("openapi: 3.0.0\npaths: {}")
        result = load_spec(f.name)
    assert result == {"openapi": "3.0.0", "paths": {}}


def test_load_yml_extension() -> None:
    """Files with .yml extension are loaded as YAML."""
    with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
        Path(f.name).write_text("openapi: 3.0.0\npaths: {}")
        result = load_spec(f.name)
    assert result == {"openapi": "3.0.0", "paths": {}}


def test_load_path_object() -> None:
    """Path objects are accepted."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        Path(f.name).write_text("{}")
        result = load_spec(Path(f.name))
    assert result == {}


def test_unsupported_format_raises() -> None:
    """Unsupported file formats raise ValueError."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        Path(f.name).write_text("{}")
        with pytest.raises(ValueError, match="Unsupported format"):
            load_spec(f.name)
