"""Parametrized tests that run with every supported backend."""

import asyncio
from collections.abc import Mapping
from http import HTTPMethod, HTTPStatus

import httpx
import httpx2
import pytest
import requests
import responses
import respx
from beartype import beartype

from openapi_mock import (
    add_openapi_to_responses,
    add_openapi_to_respx,
    create_httpx2_transport,
)

BASE_URL = "https://api.example.com"

_Response = httpx.Response | httpx2.Response | requests.Response
_RequestParams = Mapping[str, bool | float | int | str | None]


def _params_or_empty(*, params: _RequestParams | None) -> _RequestParams:
    """Return an empty request body when parameters are absent."""
    return dict[str, bool | float | int | str | None]() if params is None else params


@beartype
def _run_respx(
    *,
    spec: Mapping[str, object],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: _RequestParams | None,
) -> _Response:
    """Run a request against the respx backend."""
    with respx.mock(base_url=base_url, assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url=base_url)
        if method == HTTPMethod.GET:
            return httpx.request(method=method, url=url, params=params)
        return httpx.request(
            method=method,
            url=url,
            json=_params_or_empty(params=params),
        )


@beartype
def _run_responses(
    *,
    spec: Mapping[str, object],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: _RequestParams | None,
) -> _Response:
    """Run a request against the responses backend."""
    with responses.RequestsMock() as rsps:
        add_openapi_to_responses(spec=spec, base_url=base_url, mock=rsps)
        if method == HTTPMethod.GET:
            return requests.request(method=method, url=url, params=params, timeout=30)
        return requests.request(
            method=method,
            url=url,
            json=_params_or_empty(params=params),
            timeout=30,
        )


@beartype
def _run_httpx2(
    *,
    spec: Mapping[str, object],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: _RequestParams | None,
) -> httpx2.Response:
    """Run a request against the native HTTPX2 transport."""
    transport = create_httpx2_transport(spec=spec, base_url=base_url)
    with httpx2.Client(transport=transport) as client:
        if method == HTTPMethod.GET:
            return client.request(method=method, url=url, params=params)
        return client.request(
            method=method,
            url=url,
            json=_params_or_empty(params=params),
        )


@beartype
def _run(
    *,
    backend: str,
    spec: Mapping[str, object],
    url: str,
    base_url: str,
    method: HTTPMethod,
    params: _RequestParams | None,
) -> _Response:
    """Run a request against the given backend."""
    if backend == "respx":
        return _run_respx(
            spec=spec, url=url, base_url=base_url, method=method, params=params
        )
    if backend == "responses":
        return _run_responses(
            spec=spec, url=url, base_url=base_url, method=method, params=params
        )
    return _run_httpx2(
        spec=spec, url=url, base_url=base_url, method=method, params=params
    )


@beartype
def _setup(*, backend: str, spec: Mapping[str, object], base_url: str) -> None:
    """Set up mock from spec (no request). Verifies setup does not crash."""
    if backend == "respx":
        with respx.mock(base_url=base_url, assert_all_called=False) as m:
            add_openapi_to_respx(mock_obj=m, spec=spec, base_url=base_url)
    elif backend == "responses":
        with responses.RequestsMock() as rsps:
            add_openapi_to_responses(spec=spec, base_url=base_url, mock=rsps)
    else:
        _ = create_httpx2_transport(spec=spec, base_url=base_url)


_BACKEND = pytest.mark.parametrize(
    argnames="backend",
    argvalues=["respx", "responses", "httpx2"],
    ids=["respx", "responses", "httpx2"],
)


def test_httpx2_transport_uses_native_objects() -> None:
    """The HTTPX2 backend receives and returns native HTTPX2 objects."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"example": {"name": "Fluffy"}},
                            },
                        },
                    },
                },
            },
        },
    }
    transport = create_httpx2_transport(spec=spec, base_url=BASE_URL)

    with httpx2.Client(transport=transport) as client:
        response = client.get(url=f"{BASE_URL}/pets")

    assert isinstance(response, httpx2.Response)
    assert isinstance(response.request, httpx2.Request)
    assert response.json() == {"name": "Fluffy"}


def test_httpx2_transport_supports_async_clients() -> None:
    """The native transport can also serve an asynchronous HTTPX2 client."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "paths": {"/pets": {"get": {"responses": {"200": {}}}}},
    }
    transport = create_httpx2_transport(spec=spec, base_url=BASE_URL)

    async def request() -> httpx2.Response:
        """Make an asynchronous request through the native transport."""
        async with httpx2.AsyncClient(transport=transport) as client:
            return await client.get(url=f"{BASE_URL}/pets")

    response = asyncio.run(main=request())

    assert isinstance(response, httpx2.Response)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    argnames=("method", "path"),
    argvalues=[("POST", "/pets"), ("GET", "/missing")],
)
def test_httpx2_transport_rejects_unmatched_requests(method: str, path: str) -> None:
    """Unmatched HTTPX2 requests fail locally without network access."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "paths": {"/pets": {"get": {"responses": {"200": {}}}}},
    }
    transport = create_httpx2_transport(spec=spec, base_url=BASE_URL)

    with (
        httpx2.Client(transport=transport) as client,
        pytest.raises(
            expected_exception=httpx2.ConnectError,
            match="No OpenAPI operation matched",
        ),
    ):
        _ = client.request(method=method, url=f"{BASE_URL}{path}")


@_BACKEND
def test_empty_responses_returns_200_empty(backend: str) -> None:
    """Operation with empty responses returns 200 and empty body."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "paths": {"/pets": {"get": {"responses": {}}}},
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
        pytest.param({"paths": {"/pets": "invalid"}}, id="non_dict_path_item"),
        pytest.param({"paths": {"/pets": {"parameters": []}}}, id="non_http_method"),
        pytest.param({"paths": {"/pets": {"get": "invalid"}}}, id="non_dict_operation"),
    ],
)
def test_setup_does_not_crash(backend: str, spec: Mapping[str, object]) -> None:
    """Invalid or non-standard spec inputs are skipped without crashing."""
    _setup(backend=backend, spec=spec, base_url=BASE_URL)


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
def test_examples_fallback_to_schema(
    backend: str, examples: Mapping[str, object]
) -> None:
    """OpenAPI 3.1: examples without a usable value falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/data",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"s": "", "n": 0, "i": 0, "b": False, "x": None}


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
    params: _RequestParams | None,
    example: Mapping[str, object],
) -> None:
    """PUT, DELETE, and PATCH paths are mocked (both backends)."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets/1": {
                method.value.lower(): {
                    "responses": {
                        "200": {
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
        pytest.param({"schema": True}, id="non_dict_schema"),
        pytest.param("invalid", id="non_dict_json_content"),
    ],
)
def test_missing_or_invalid_content_returns_empty(
    backend: str, json_content: object
) -> None:
    """Missing or invalid application/json content returns 200 with empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/data",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"valid": ""}


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
def test_skips_invalid(backend: str) -> None:
    """Skips non-dict path items and non-HTTP methods."""
    spec: Mapping[str, object] = {
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
    resp = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/valid",
        base_url=BASE_URL,
        method=HTTPMethod.GET,
        params=None,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


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
def test_spec_with_info(backend: str) -> None:
    """Spec with info field parses correctly."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "My API", "version": "1.0.0"},
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
def test_no_paths_key(backend: str) -> None:
    """Spec with no paths key does not crash."""
    spec: Mapping[str, object] = {"openapi": "3.0.0"}
    _setup(backend=backend, spec=spec, base_url=BASE_URL)


@_BACKEND
def test_operation_responses_not_dict(backend: str) -> None:
    """Operation with non-dict responses is still registered."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {"responses": "invalid"},
            },
        },
    }
    _setup(backend=backend, spec=spec, base_url=BASE_URL)


@_BACKEND
def test_path_item_unknown_key(backend: str) -> None:
    """Unknown keys (e.g. x-extensions) on path items are ignored."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "x-custom": "extension",
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
    argnames="method",
    argvalues=[HTTPMethod.HEAD, HTTPMethod.OPTIONS, HTTPMethod.TRACE],
)
def test_head_options_and_trace_operations(
    backend: str,
    method: HTTPMethod,
) -> None:
    """HEAD, OPTIONS, and TRACE operations are registered."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                method.value.lower(): {
                    "responses": {
                        "200": {
                            "description": "OK",
                        },
                    },
                },
            },
        },
    }
    response = _run(
        backend=backend,
        spec=spec,
        url=f"{BASE_URL}/pets",
        base_url=BASE_URL,
        method=method,
        params=None,
    )

    assert response.status_code == HTTPStatus.OK


@_BACKEND
def test_unparseable_spec(backend: str) -> None:
    """Spec that fails model_validate after preprocessing does not crash."""
    spec: Mapping[str, object] = {
        "openapi": "3.0.0",
        "servers": "invalid",
        "paths": {},
    }
    _setup(backend=backend, spec=spec, base_url=BASE_URL)


@_BACKEND
def test_ref_schema_bad_prefix(backend: str) -> None:
    """Schema $ref with unexpected prefix skips the property."""
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
                                            "pet": {
                                                "$ref": "#/definitions/Pet",
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
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
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
def test_ref_array_items_unresolvable(backend: str) -> None:
    """Array items with unresolvable $ref returns empty array."""
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
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/Missing",
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
    assert resp.json() == []


@_BACKEND
def test_ref_response_no_components(backend: str) -> None:
    """Response $ref with no components returns empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {"$ref": "#/components/responses/Missing"},
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
def test_ref_response_bad_prefix(backend: str) -> None:
    """Response $ref with unexpected prefix returns empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {"$ref": "#/definitions/MyResponse"},
                    },
                },
            },
        },
        "components": {
            "responses": {
                "MyResponse": {
                    "description": "OK",
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
def test_ref_example_no_value(backend: str) -> None:
    """Example $ref that resolves but has no value falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "pet": {
                                            "$ref": "#/components/examples/NoValue",
                                        },
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {
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
        "components": {
            "examples": {
                "NoValue": {
                    "summary": "Example with no value",
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
    assert resp.json() == {"name": ""}


@_BACKEND
def test_ref_example_no_components(backend: str) -> None:
    """Example $ref with no components falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "pet": {
                                            "$ref": "#/components/examples/Missing",
                                        },
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
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
    assert resp.json() == {"id": 0}


@_BACKEND
def test_ref_example_bad_prefix(backend: str) -> None:
    """Example $ref with unexpected prefix falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "pet": {
                                            "$ref": "#/definitions/MyExample",
                                        },
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "examples": {
                "MyExample": {
                    "value": {"id": 5},
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
def test_ref_response_double_ref(backend: str) -> None:
    """Response component that itself is a $ref returns empty body."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {"$ref": "#/components/responses/Alias"},
                    },
                },
            },
        },
        "components": {
            "responses": {
                "Alias": {"$ref": "#/components/responses/Actual"},
                "Actual": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "example": {"id": 1},
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
def test_ref_example_double_ref(backend: str) -> None:
    """Example component that itself is a $ref falls back to schema."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "pet": {
                                            "$ref": "#/components/examples/Alias",
                                        },
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "examples": {
                "Alias": {"$ref": "#/components/examples/Actual"},
                "Actual": {
                    "value": {"id": 5},
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
def test_ref_schema_in_response(backend: str) -> None:
    """Schema $ref in response content is resolved."""
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
                                        "$ref": "#/components/schemas/Pet",
                                    },
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


@_BACKEND
def test_ref_response(backend: str) -> None:
    """Response $ref is resolved."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {"$ref": "#/components/responses/PetResponse"},
                    },
                },
            },
        },
        "components": {
            "responses": {
                "PetResponse": {
                    "description": "A pet",
                    "content": {
                        "application/json": {
                            "example": {"id": 1, "name": "Rex"},
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
    assert resp.json() == {"id": 1, "name": "Rex"}


@_BACKEND
def test_ref_nested_schema_property(backend: str) -> None:
    """Schema property $ref is resolved."""
    spec = {
        "openapi": "3.0.0",
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
                                            "pet": {
                                                "$ref": "#/components/schemas/Pet",
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
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
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
    assert resp.json() == {"pet": {"name": ""}}


@_BACKEND
def test_ref_array_items(backend: str) -> None:
    """Array items $ref is resolved."""
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
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/Pet",
                                        },
                                    },
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
                    "properties": {"name": {"type": "string"}},
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
    assert resp.json() == [{"name": ""}]


@_BACKEND
def test_ref_example(backend: str) -> None:
    """Example $ref is resolved."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "pet": {
                                            "$ref": "#/components/examples/PetExample",
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "examples": {
                "PetExample": {
                    "summary": "A pet",
                    "value": {"id": 5, "name": "Buddy"},
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
    assert resp.json() == {"id": 5, "name": "Buddy"}


@_BACKEND
def test_ref_unresolvable_returns_empty(backend: str) -> None:
    """Unresolvable $ref returns empty body."""
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
                                        "$ref": "#/components/schemas/Missing",
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
    assert resp.json() == {}
