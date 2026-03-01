"""Tests for openapi_mock."""

import httpx
import respx

from openapi_mock import add_openapi_to_respx


def test_simple_path() -> None:
    """A simple GET path is mocked."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {"description": "OK"}}},
            },
        },
    }
    with respx.mock(
        base_url="https://api.example.com",
        assert_all_called=False,
    ) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/pets")
    assert response.status_code == 200
    assert response.json() == {}


def test_skips_non_dict_path_item() -> None:
    """Non-dict path items are skipped."""
    spec = {"paths": {"/pets": "invalid"}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
    # No route added, nothing to assert


def test_skips_non_http_methods() -> None:
    """Non-HTTP methods are skipped."""
    spec = {"paths": {"/pets": {"parameters": []}}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
    # No route added


def test_skips_non_dict_operation() -> None:
    """Non-dict operations are skipped."""
    spec = {"paths": {"/pets": {"get": "invalid"}}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
    # No route added


def test_uses_example_when_present() -> None:
    """Response example is used when present in spec."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    },
                                    "example": {"id": 1, "name": "Fluffy"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    with respx.mock(
        base_url="https://api.example.com",
        assert_all_called=False,
    ) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/pets")
    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Fluffy"}


def test_generates_from_schema_when_no_example() -> None:
    """Mock data is generated from schema when no example is present."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    with respx.mock(
        base_url="https://api.example.com",
        assert_all_called=False,
    ) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/pets")
    assert response.status_code == 200
    assert response.json() == {"id": 0, "name": ""}


def test_nested_schema_generation() -> None:
    """Nested objects and arrays are generated from schema."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "users": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"}
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    with respx.mock(
        base_url="https://api.example.com",
        assert_all_called=False,
    ) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/users")
    assert response.status_code == 200
    assert response.json() == {"users": [{"name": ""}]}
