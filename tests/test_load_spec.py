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


def test_load_yaml(tmp_path: Path) -> None:
    """YAML files are loaded correctly."""
    path = tmp_path / "spec.yaml"
    path.write_text(data="openapi: 3.0.0\npaths: {}")
    result = load_spec(path=path)
    assert result == {"openapi": "3.0.0", "paths": {}}


def test_load_yml_extension(tmp_path: Path) -> None:
    """Files with .yml extension are loaded as YAML."""
    path = tmp_path / "spec.yml"
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


def test_empty_yaml_raises(tmp_path: Path) -> None:
    """Empty YAML files raise ValueError."""
    path = tmp_path / "spec.yaml"
    path.write_text(data="")
    with pytest.raises(expected_exception=ValueError, match="Empty or null YAML spec"):
        load_spec(path=path)


def test_null_yaml_raises(tmp_path: Path) -> None:
    """YAML files containing only null raise ValueError."""
    path = tmp_path / "spec.yaml"
    path.write_text(data="null")
    with pytest.raises(expected_exception=ValueError, match="Empty or null YAML spec"):
        load_spec(path=path)
