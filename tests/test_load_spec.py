"""Tests for load_spec."""

from pathlib import Path

import httpx
import pytest
import respx

from openapi_mock import add_openapi_to_respx, load_spec

# Minimal valid OpenAPI 3.0 spec (info.title and info.version are required)
_MINIMAL_SPEC = (
    '{"openapi": "3.0.0", "info": {"title": "API", "version": "1.0"}, "paths": {}}'
)
_MINIMAL_YAML = 'openapi: 3.0.0\ninfo:\n  title: API\n  version: "1.0"\npaths: {}'


def test_load_json(tmp_path: Path) -> None:
    """JSON files are loaded correctly."""
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "API", "version": "1.0"},
        "paths": {},
    }
    path = tmp_path / "spec.json"
    path.write_text(data=_MINIMAL_SPEC)
    result = load_spec(path=path)
    assert result == spec_data


def test_load_yaml(tmp_path: Path) -> None:
    """YAML files are loaded correctly."""
    path = tmp_path / "spec.yaml"
    path.write_text(data=_MINIMAL_YAML)
    result = load_spec(path=path)
    assert result["openapi"] == "3.0.0"
    assert result["info"]["title"] == "API"
    assert result["paths"] == {}


def test_load_yml_extension(tmp_path: Path) -> None:
    """Files with .yml extension are loaded as YAML."""
    path = tmp_path / "spec.yml"
    path.write_text(data=_MINIMAL_YAML)
    result = load_spec(path=path)
    assert result["openapi"] == "3.0.0"
    assert result["paths"] == {}


def test_load_path_object(tmp_path: Path) -> None:
    """Path objects are accepted."""
    path = tmp_path / "spec.json"
    path.write_text(data=_MINIMAL_SPEC)
    result = load_spec(path=path)
    assert "openapi" in result


def test_load_spec_integration_with_respx(tmp_path: Path) -> None:
    """Loaded spec works with add_openapi_to_respx."""
    path = tmp_path / "spec.json"
    path.write_text(
        data='{"openapi": "3.0.0", "info": {"title": "API", "version": "1.0"}, "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK", "content": {"application/json": {"example": {"id": 1}}}}}}}}}'
    )
    spec = load_spec(path=path)
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        resp = httpx.get(url="https://api.example.com/pets")
    assert resp.status_code == 200
    assert resp.json() == {"id": 1}


def test_file_not_found_raises() -> None:
    """Non-existent file raises FileNotFoundError."""
    with pytest.raises(expected_exception=FileNotFoundError, match="not found"):
        load_spec(path="/nonexistent/spec.json")


def test_ref_resolution(tmp_path: Path) -> None:
    """$ref references are resolved by prance."""
    components = tmp_path / "components.yaml"
    components.write_text(
        data="""components:
  schemas:
    Pet:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
"""
    )
    # Use file ref - prance resolves relative to spec file
    ref_spec = tmp_path / "ref_spec.yaml"
    ref_spec.write_text(
        data="""openapi: 3.0.0
info:
  title: API
  version: "1.0"
paths:
  /pets:
    get:
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "./components.yaml#/components/schemas/Pet"
"""
    )
    result = load_spec(path=ref_spec)
    # After resolution, schema should be inlined (no $ref)
    schema = result["paths"]["/pets"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert "$ref" not in str(object=schema)
    assert schema.get("type") == "object"
    assert "properties" in schema
    assert "id" in schema["properties"]
    assert "name" in schema["properties"]
