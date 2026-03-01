"""Tests for openapi_mock."""

from http import HTTPStatus

import httpx
import respx

from openapi_mock import add_openapi_to_respx


def test_empty_responses_returns_200_empty() -> None:
    """Operation with empty responses returns 200 and empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {"responses": {}},
            },
        },
    }
    with respx.mock(
        base_url="https://api.example.com",
        assert_all_called=False,
    ) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/pets")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_yaml_integer_status_keys() -> None:
    """YAML unquoted status keys (200:) become ints; must not crash."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        200: {
                            "content": {
                                "application/json": {
                                    "example": {"id": 1},
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": 1}


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
    assert response.status_code == HTTPStatus.OK
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": 0, "name": ""}


def test_schema_primitives() -> None:
    """All schema primitive types generate correct placeholders."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "s": {"type": "string"},
                                            "n": {"type": "number"},
                                            "i": {"type": "integer"},
                                            "b": {"type": "boolean"},
                                            "x": {"type": "null"},
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
        response = httpx.get("https://api.example.com/data")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"s": "", "n": 0, "i": 0, "b": False, "x": None}


def test_array_without_items() -> None:
    """Array schema without items returns empty array."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array"},
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
        response = httpx.get("https://api.example.com/items")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


def test_prefers_201_response() -> None:
    """201 is used when 200 is not available."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "post": {
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {
                                    "example": {"id": 42},
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
        response = httpx.post("https://api.example.com/pets", json={})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == {"id": 42}


def test_prefers_first_2xx_when_no_200_or_201() -> None:
    """First 2xx status is used when 200/201 not present."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "204": {"description": "No content"},
                        "404": {"description": "Not found"},
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
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.json() == {}


def test_content_without_schema_or_example() -> None:
    """Empty object when content has neither schema nor example."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {},
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_unknown_schema_type_returns_empty_object() -> None:
    """Unknown or missing schema type returns empty object."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {},
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
        response = httpx.get("https://api.example.com/data")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_schema_non_dict_returns_empty() -> None:
    """Non-dict schema (e.g. OpenAPI 3.1 boolean true) does not crash."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": True,
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_object_skips_non_dict_property_schema() -> None:
    """Object properties with non-dict schema are skipped."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "valid": {"type": "string"},
                                            "invalid": "not a schema",
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
        response = httpx.get("https://api.example.com/data")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"valid": ""}


def test_response_not_dict_returns_empty() -> None:
    """When response value is not a dict, returns empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": "invalid",
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_non_standard_status_code_returns_int() -> None:
    """Non-standard status codes (e.g. 522) fall back to int."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "522": {
                            "description": "Connection timed out",
                            "content": {
                                "application/json": {
                                    "example": {"error": "Timeout"},
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
    assert response.status_code == 522
    assert response.json() == {"error": "Timeout"}


def test_default_response_key_when_no_2xx() -> None:
    """Uses default response (mapped to 200) when only default exists."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "default": {
                            "description": "Fallback",
                            "content": {
                                "application/json": {
                                    "example": {"error": "Something went wrong"},
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"error": "Something went wrong"}


def test_first_response_when_no_2xx() -> None:
    """Uses first response when no 2xx status exists."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "404": {
                            "content": {
                                "application/json": {
                                    "example": {"error": "Not found"},
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
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"error": "Not found"}


def test_json_content_not_dict_returns_empty() -> None:
    """When application/json content is not a dict, returns empty."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": "invalid",
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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


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
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"users": [{"name": ""}]}
