"""Tests for load_spec."""

from pathlib import Path

import pytest

from openapi_mock import load_spec


def test_load_json(tmp_path: Path) -> None:
    """JSON files are loaded correctly."""
    spec = {"openapi": "3.0.0", "paths": {}}
    path = tmp_path / "spec.json"
    path.write_text(data='{"openapi": "3.0.0", "paths": {}}')
    result = load_spec(path=path)
    assert result == spec


@pytest.mark.parametrize("extension", [".yaml", ".yml"])
def test_load_yaml(tmp_path: Path, extension: str) -> None:
    """YAML and YML files are loaded correctly."""
    path = tmp_path / f"spec{extension}"
    path.write_text(data="openapi: 3.0.0\npaths: {}")
    result = load_spec(path=path)
    assert result == {"openapi": "3.0.0", "paths": {}}


def test_load_path_object(tmp_path: Path) -> None:
    """Path objects are accepted."""
    path = tmp_path / "spec.json"
    path.write_text(data="{}")
    result = load_spec(path=path)
    assert result == {}


def test_unsupported_format_raises(tmp_path: Path) -> None:
    """Unsupported file formats raise ValueError."""
    path = tmp_path / "spec.txt"
    path.write_text(data="{}")
    with pytest.raises(expected_exception=ValueError, match="Unsupported format"):
        load_spec(path=path)


@pytest.mark.parametrize("content", ["", "null"], ids=["empty", "null"])
def test_invalid_yaml_raises(tmp_path: Path, content: str) -> None:
    """Empty or null YAML files raise ValueError."""
    path = tmp_path / "spec.yaml"
    path.write_text(data=content)
    with pytest.raises(expected_exception=ValueError, match="Empty or null YAML spec"):
        load_spec(path=path)
