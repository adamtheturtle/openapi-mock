"""Parametrized tests that run with both respx and responses backends."""

from http import HTTPStatus

import httpx
import pytest
import requests
import respx
import responses

from openapi_mock import add_openapi_to_respx, add_openapi_to_responses

BASE_URL = "https://api.example.com"


def _run_respx(
    spec: dict, url: str, method: str = "GET", params: dict | None = None
) -> tuple[int, object]:
    """Run a request against the respx backend."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as m:
        add_openapi_to_respx(mock_obj=m, spec=spec, base_url=BASE_URL)
        if method == "GET":
            resp = httpx.get(url=url, params=params)
        else:
            resp = httpx.post(url=url, json=params or {})
    return resp.status_code, resp.json()


def _run_responses(
    spec: dict, url: str, method: str = "GET", params: dict | None = None
) -> tuple[int, object]:
    """Run a request against the responses backend."""
    with responses.RequestsMock() as rsps:
        add_openapi_to_responses(spec=spec, base_url=BASE_URL, mock=rsps)
        if method == "GET":
            resp = requests.get(url, params=params)
        else:
            resp = requests.post(url, json=params or {})
    return resp.status_code, resp.json()


def _run(
    backend: str, spec: dict, url: str, method: str = "GET", params: dict | None = None
) -> tuple[int, object]:
    """Run a request against the given backend."""
    if backend == "respx":
        return _run_respx(spec=spec, url=url, method=method, params=params)
    return _run_responses(spec=spec, url=url, method=method, params=params)


@pytest.mark.parametrize("backend", ["respx", "responses"])
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


@pytest.mark.parametrize("backend", ["respx", "responses"])
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


@pytest.mark.parametrize("backend", ["respx", "responses"])
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
                                "application/json": {"example": {"version": "1.0"}},
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


@pytest.mark.parametrize("backend", ["respx", "responses"])
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
                                "application/json": {"schema": {"type": "array"}},
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


@pytest.mark.parametrize("backend", ["respx", "responses"])
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
