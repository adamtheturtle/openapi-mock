"""Parametrized tests that run with both respx and responses backends."""

from http import HTTPMethod, HTTPStatus
from typing import Any

import httpx
import pytest
import requests
import respx
import responses
from beartype import beartype

from openapi_mock import add_openapi_to_respx, add_openapi_to_responses

BASE_URL = "https://api.example.com"
INFO = {"title": "API", "version": "1.0.0"}

_Response = httpx.Response | requests.Response


@beartype
def _run_respx(
    *,
    spec: dict[str, Any],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: dict[str, Any] | None,
) -> _Response:
    """Run a request against the respx backend."""
    with respx.mock(base_url=base_url, assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url=base_url)
        if method == HTTPMethod.GET:
            return httpx.request(method=method, url=url, params=params)
        return httpx.request(method=method, url=url, json=params or {})


@beartype
def _run_responses(
    *,
    spec: dict[str, Any],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: dict[str, Any] | None,
) -> _Response:
    """Run a request against the responses backend."""
    with responses.RequestsMock() as rsps:
        add_openapi_to_responses(spec=spec, base_url=base_url, mock=rsps)
        if method == HTTPMethod.GET:
            return requests.request(method=method, url=url, params=params, timeout=30)
        return requests.request(method=method, url=url, json=params or {}, timeout=30)


@beartype
def _run(
    *,
    backend: str,
    spec: dict[str, Any],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: dict[str, Any] | None,
) -> _Response:
    """Run a request against the given backend."""
    if backend == "respx":
        return _run_respx(
            spec=spec, url=url, base_url=base_url, method=method, params=params
        )
    return _run_responses(
        spec=spec, url=url, base_url=base_url, method=method, params=params
    )


@beartype
def _setup(*, backend: str, spec: dict[str, Any], base_url: str) -> None:
    """Set up mock from spec (no request). Verifies setup does not crash."""
    if backend == "respx":
        with respx.mock(base_url=base_url, assert_all_called=False) as m:
            add_openapi_to_respx(mock_obj=m, spec=spec, base_url=base_url)
    else:
        with responses.RequestsMock() as rsps:
            add_openapi_to_responses(spec=spec, base_url=base_url, mock=rsps)


_BACKEND = pytest.mark.parametrize(
    argnames="backend", argvalues=["respx", "responses"], ids=["respx", "responses"]
)


@_BACKEND
def test_empty_responses_returns_200_empty(backend: str) -> None:
    """Operation with minimal responses (no content) returns 200 and empty body."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


@_BACKEND
def test_simple_path(backend: str) -> None:
    """A simple GET path is mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                            },
                        },
                    },
                },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


@_BACKEND
def test_simple_path_description_only(backend: str) -> None:
    """A simple GET path with description only returns 200 and empty body."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {"description": "OK"}}},
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


@_BACKEND
def test_yaml_integer_status_keys(backend: str) -> None:
    """YAML unquoted status keys (200:) become ints; normalized to strings."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 1}


@_BACKEND
@pytest.mark.parametrize(
    argnames="spec",
    argvalues=[
        pytest.param(
            {"openapi": "3.0.0", "info": INFO, "paths": {"/pets": "invalid"}},
            id="non_dict_path_item",
        ),
        pytest.param(
            {
                "openapi": "3.0.0",
                "info": INFO,
                "paths": {"/pets": {"get": "invalid"}},
            },
            id="non_dict_operation",
        ),
    ],
)
def test_invalid_spec_raises(backend: str, spec: dict[str, Any]) -> None:
    """Invalid specs raise from openapi-core validation."""
    with pytest.raises(Exception):
        _setup(backend=backend, spec=spec, base_url=BASE_URL)


@_BACKEND
def test_uses_example_when_present(backend: str) -> None:
    """Response example is used when present in spec."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 1, "name": "Fluffy"}


@_BACKEND
def test_uses_examples_when_no_example(backend: str) -> None:
    """OpenAPI 3.1: examples (plural) - use first example's value."""
    spec = {
        "openapi": "3.1.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 10, "name": "Max"}


@_BACKEND
@pytest.mark.parametrize(
    argnames="examples",
    argvalues=[
        pytest.param({}, id="empty_examples"),
        pytest.param(
            {
                "external": {
                    "summary": "External only",
                    "externalValue": "https://example.com/pet.json",
                },
            },
            id="external_value_only",
        ),
    ],
)
def test_examples_fallback_to_schema(backend: str, examples: dict[str, Any]) -> None:
    """OpenAPI 3.1: examples without a usable value falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": examples,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 0}


@_BACKEND
def test_generates_from_schema_when_no_example(backend: str) -> None:
    """Mock data is generated from schema when no example is present."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 0, "name": ""}


@_BACKEND
def test_path_param(backend: str) -> None:
    """Path params are matched (respx natively, responses via regex)."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets/42",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 1, "name": "Fluffy"}


@_BACKEND
def test_path_with_dots(backend: str) -> None:
    """Literal path segments (e.g. v1.0) match exactly."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/api/v1.0/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/api/v1.0/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"version": "1.0"}


@_BACKEND
def test_schema_primitives(backend: str) -> None:
    """All schema primitive types generate correct placeholders."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "s": {"type": "string"},
                                            "n": {"type": "number"},
                                            "i": {"type": "integer"},
                                            "b": {"type": "boolean"},
                                            "x": {"type": "string", "nullable": True},
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/data",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"s": "", "n": 0, "i": 0, "b": False, "x": ""}


@_BACKEND
def test_schema_type_array_openapi_31(backend: str) -> None:
    """OpenAPI 3.1: type as array e.g. ['string', 'null'] uses first non-null."""
    spec = {
        "openapi": "3.1.0",
        "info": INFO,
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/data",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"name": "", "count": 0}


@_BACKEND
def test_array_without_items(backend: str) -> None:
    """Array schema without items returns empty array."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/items",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


@_BACKEND
def test_post_path(backend: str) -> None:
    """A POST path is mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "post": {
                    "responses": {
                        "201": {
                            "description": "Created",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.POST,
        params={"name": "Fluffy"},
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json() == {"id": 1, "name": "Fluffy"}


@_BACKEND
@pytest.mark.parametrize(
    argnames=("method", "params", "example"),
    argvalues=[
        (HTTPMethod.PUT, {"name": "Updated"}, {"id": 1, "name": "Updated"}),
        (HTTPMethod.DELETE, None, {"deleted": True}),
        (HTTPMethod.PATCH, {"name": "Patched"}, {"id": 1, "name": "Patched"}),
    ],
    ids=["put", "delete", "patch"],
)
def test_mutating_path(
    backend: str,
    method: HTTPMethod,
    params: dict[str, Any] | None,
    example: dict[str, Any],
) -> None:
    """PUT, DELETE, and PATCH paths are mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets/1": {
                    method.value.lower(): {
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "example": example,
                                    },
                                },
                            },
                        },
                    },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets/1",
        base_url=BASE_URL,
        method=method,
        params=params,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == example


@_BACKEND
def test_prefers_201_response(backend: str) -> None:
    """201 is used when 200 is not available."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "post": {
                    "responses": {
                        "201": {
                            "description": "Created",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.POST,
        params={},
    )
    assert resp.status_code == HTTPStatus.CREATED
    assert resp.json() == {"id": 42}


@_BACKEND
def test_query_params(backend: str) -> None:
    """URLs with query strings (e.g. ?limit=10) are matched."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params={"limit": 10},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


@_BACKEND
def test_prefers_first_2xx_when_no_200_or_201(backend: str) -> None:
    """First 2xx status is used when 200/201 not present."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json() == {"status": "pending"}


@_BACKEND
@pytest.mark.parametrize(
    argnames="json_content",
    argvalues=[
        pytest.param({}, id="empty_content"),
        pytest.param({"schema": {}}, id="unknown_schema_type"),
    ],
)
def test_missing_or_invalid_content_returns_empty(
    backend: str, json_content: Any
) -> None:
    """Missing or invalid application/json content returns 200 with empty body."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": json_content,
                            },
                        },
                    },
                },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


@_BACKEND
def test_non_standard_status_code_returns_int(backend: str) -> None:
    """Non-standard status codes (e.g. 522) fall back to int."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == 522
    assert resp.json() == {"error": "Timeout"}


@_BACKEND
def test_default_response_key_when_no_2xx(backend: str) -> None:
    """Uses default response (mapped to 200) when only default exists."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"error": "Something went wrong"}


@_BACKEND
def test_first_response_when_no_2xx(backend: str) -> None:
    """Uses first response when no 2xx status exists."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "404": {
                            "description": "Not found",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {"error": "Not found"}


@_BACKEND
def test_nested_schema_generation(backend: str) -> None:
    """Nested objects and arrays are generated from schema."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/users",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"users": [{"name": ""}]}


@_BACKEND
def test_openapi_core_validates_compliant_spec(backend: str) -> None:
    """Fully compliant OpenAPI spec is validated by openapi-core."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Petstore", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "List of pets",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"type": "object"}},
                                    "example": [{"id": 1, "name": "Fluffy"}],
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == [{"id": 1, "name": "Fluffy"}]


@_BACKEND
def test_schema_type_null_openapi_31(backend: str) -> None:
    """OpenAPI 3.1: type 'null' generates None."""
    spec = {
        "openapi": "3.1.0",
        "info": INFO,
        "paths": {
            "/data": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "value": {"type": "null"},
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/data",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"value": None}


@_BACKEND
def test_skips_non_http_methods(backend: str) -> None:
    """Path items with parameters/summary etc. are skipped; only HTTP methods are mocked."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"example": {"pets": []}}},
                        },
                    },
                },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"pets": []}


@_BACKEND
def test_schema_ref_resolution(backend: str) -> None:
    """$ref in schemas is resolved via openapi-core for mock generation."""
    spec = {
        "openapi": "3.0.0",
        "info": INFO,
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "List of pets",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"},
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                },
            },
        },
    }
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 0, "name": ""}
