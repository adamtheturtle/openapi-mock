"""Parametrized tests that run with both respx and responses backends."""

from http import HTTPStatus
from typing import Any

import httpx
import pytest
import requests
import respx
import responses
from beartype import beartype

from openapi_mock import add_openapi_to_respx, add_openapi_to_responses

BASE_URL = "https://api.example.com"


@beartype
def _run_respx(
    *,
    spec: dict[str, Any],
    url: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
) -> tuple[int, object]:
    """Run a request against the respx backend."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url=BASE_URL)
        if method == "GET":
            resp = httpx.get(url=url, params=params)
        else:
            resp = httpx.post(url=url, json=params or {})
    return resp.status_code, resp.json()


@beartype
def _run_responses(
    *,
    spec: dict[str, Any],
    url: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
) -> tuple[int, object]:
    """Run a request against the responses backend."""
    with responses.RequestsMock() as rsps:
        add_openapi_to_responses(spec=spec, base_url=BASE_URL, mock=rsps)
        if method == "GET":
            resp = requests.get(url=url, params=params, timeout=30)
        else:
            resp = requests.post(url=url, json=params or {}, timeout=30)
    return resp.status_code, resp.json()


@beartype
def _run(
    *,
    backend: str,
    spec: dict[str, Any],
    url: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
) -> tuple[int, object]:
    """Run a request against the given backend."""
    if backend == "respx":
        return _run_respx(spec=spec, url=url, method=method, params=params)
    return _run_responses(spec=spec, url=url, method=method, params=params)


@beartype
def _setup(*, backend: str, spec: dict[str, Any]) -> None:
    """Set up mock from spec (no request). Verifies setup does not crash."""
    if backend == "respx":
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as m:
            add_openapi_to_respx(mock_obj=m, spec=spec, base_url=BASE_URL)
    else:
        with responses.RequestsMock() as rsps:
            add_openapi_to_responses(spec=spec, base_url=BASE_URL, mock=rsps)


_BACKEND = pytest.mark.parametrize(
    argnames="backend", argvalues=["respx", "responses"], ids=["respx", "responses"]
)


@_BACKEND
def test_empty_responses_returns_200_empty(backend: str) -> None:
    """Operation with empty responses returns 200 and empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {"/pets": {"get": {"responses": {}}}},
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_simple_path(backend: str) -> None:
    """A simple GET path is mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_simple_path_description_only(backend: str) -> None:
    """A simple GET path with description only returns 200 and empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {"description": "OK"}}},
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_yaml_integer_status_keys(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 1}


@_BACKEND
def test_skips_non_dict_path_item(backend: str) -> None:
    """Non-dict path items are skipped."""
    spec = {"paths": {"/pets": "invalid"}}
    _setup(backend=backend, spec=spec)


@_BACKEND
def test_skips_non_http_methods(backend: str) -> None:
    """Non-HTTP methods are skipped."""
    spec: dict[str, object] = {"paths": {"/pets": {"parameters": []}}}
    _setup(backend=backend, spec=spec)


@_BACKEND
def test_skips_non_dict_operation(backend: str) -> None:
    """Non-dict operations are skipped."""
    spec = {"paths": {"/pets": {"get": "invalid"}}}
    _setup(backend=backend, spec=spec)


@_BACKEND
def test_uses_example_when_present(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 1, "name": "Fluffy"}


@_BACKEND
def test_uses_examples_when_no_example(backend: str) -> None:
    """OpenAPI 3.1: examples (plural) - use first example's value."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "first": {
                                            "summary": "First example",
                                            "value": {"id": 10, "name": "Max"},
                                        },
                                        "second": {
                                            "summary": "Second example",
                                            "value": {"id": 20},
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 10, "name": "Max"}


@_BACKEND
def test_examples_empty_falls_back_to_schema(backend: str) -> None:
    """OpenAPI 3.1: empty examples dict falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "examples": {},
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 0}


@_BACKEND
def test_examples_without_value_falls_back_to_schema(backend: str) -> None:
    """OpenAPI 3.1: examples with only externalValue falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "external": {
                                            "summary": "External only",
                                            "externalValue": "https://example.com/pet.json",
                                        },
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 0}


@_BACKEND
def test_generates_from_schema_when_no_example(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"id": 0, "name": ""}


@_BACKEND
def test_path_param(backend: str) -> None:
    """Path params are matched (respx natively, responses via regex)."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {"id": 1, "name": "Fluffy"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets/42")
    assert status == HTTPStatus.OK
    assert body == {"id": 1, "name": "Fluffy"}


@_BACKEND
def test_path_with_dots(backend: str) -> None:
    """Literal path segments (e.g. v1.0) match exactly."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/api/v1.0/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {"version": "1.0"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/api/v1.0/pets")
    assert status == HTTPStatus.OK
    assert body == {"version": "1.0"}


@_BACKEND
def test_schema_primitives(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/data")
    assert status == HTTPStatus.OK
    assert body == {"s": "", "n": 0, "i": 0, "b": False, "x": None}


@_BACKEND
def test_schema_type_array_openapi_31(backend: str) -> None:
    """OpenAPI 3.1: type as array e.g. ['string', 'null'] uses first non-null."""
    spec = {
        "openapi": "3.1.0",
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
                                            "name": {"type": ["string", "null"]},
                                            "count": {"type": ["integer", "null"]},
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/data")
    assert status == HTTPStatus.OK
    assert body == {"name": "", "count": 0}


@_BACKEND
def test_array_without_items(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/items")
    assert status == HTTPStatus.OK
    assert body == []


@_BACKEND
def test_post_path(backend: str) -> None:
    """A POST path is mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "post": {
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {
                                    "example": {"id": 1, "name": "Fluffy"}
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    status, body = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        method="POST",
        params={"name": "Fluffy"},
    )
    assert status == HTTPStatus.CREATED
    assert body == {"id": 1, "name": "Fluffy"}


@_BACKEND
def test_prefers_201_response(backend: str) -> None:
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
    status, body = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        method="POST",
        params={},
    )
    assert status == HTTPStatus.CREATED
    assert body == {"id": 42}


@_BACKEND
def test_query_params(backend: str) -> None:
    """URLs with query strings (e.g. ?limit=10) are matched."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
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
    status, body = _run(
        backend=backend, spec=spec, url=f"{BASE_URL}/pets", params={"limit": 10}
    )
    assert status == HTTPStatus.OK
    assert body == []


@_BACKEND
def test_prefers_first_2xx_when_no_200_or_201(backend: str) -> None:
    """First 2xx status is used when 200/201 not present."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "202": {
                            "description": "Accepted",
                            "content": {
                                "application/json": {
                                    "example": {"status": "pending"},
                                },
                            },
                        },
                        "404": {"description": "Not found"},
                    },
                },
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.ACCEPTED
    assert body == {"status": "pending"}


@_BACKEND
def test_content_without_schema_or_example(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_unknown_schema_type_returns_empty_object(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/data")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_schema_non_dict_returns_empty(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_object_skips_non_dict_property_schema(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/data")
    assert status == HTTPStatus.OK
    assert body == {"valid": ""}


@_BACKEND
def test_response_not_dict_returns_empty(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_non_standard_status_code_returns_int(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == 522
    assert body == {"error": "Timeout"}


@_BACKEND
def test_default_response_key_when_no_2xx(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {"error": "Something went wrong"}


@_BACKEND
def test_first_response_when_no_2xx(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.NOT_FOUND
    assert body == {"error": "Not found"}


@_BACKEND
def test_json_content_not_dict_returns_empty(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/pets")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_skips_invalid(backend: str) -> None:
    """Skips non-dict path items and non-HTTP methods."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/valid": {
                "get": {"responses": {"200": {"description": "OK"}}},
            },
            "/invalid-path": "not a dict",
            "/params": {
                "parameters": [],
            },
            "/bad-op": {
                "get": "invalid",
            },
        },
    }
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/valid")
    assert status == HTTPStatus.OK
    assert body == {}


@_BACKEND
def test_nested_schema_generation(backend: str) -> None:
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
    status, body = _run(backend=backend, spec=spec, url=f"{BASE_URL}/users")
    assert status == HTTPStatus.OK
    assert body == {"users": [{"name": ""}]}
