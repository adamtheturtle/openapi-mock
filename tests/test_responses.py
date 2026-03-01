"""Tests for add_openapi_to_responses."""

from http import HTTPStatus

import requests
import responses

from openapi_mock import add_openapi_to_responses


@responses.activate
def test_add_openapi_to_responses_simple() -> None:
    """Add_openapi_to_responses adds mocks for GET /pets."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        },
                    },
                },
            },
        },
    }
    add_openapi_to_responses(spec=spec, base_url="https://api.example.com")
    resp = requests.get(url="https://api.example.com/pets", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}


@responses.activate
def test_add_openapi_to_responses_path_param() -> None:
    """Add_openapi_to_responses matches path params with regex."""
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
    add_openapi_to_responses(spec=spec, base_url="https://api.example.com")
    resp = requests.get(url="https://api.example.com/pets/42", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": 1, "name": "Fluffy"}


@responses.activate
def test_add_openapi_to_responses_path_with_dots() -> None:
    """Literal path segments (e.g. v1.0) are regex-escaped and match exactly."""
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
    add_openapi_to_responses(spec=spec, base_url="https://api.example.com")
    resp = requests.get(url="https://api.example.com/api/v1.0/pets", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"version": "1.0"}


@responses.activate
def test_add_openapi_to_responses_query_params() -> None:
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
    add_openapi_to_responses(spec=spec, base_url="https://api.example.com")
    resp = requests.get(
        url="https://api.example.com/pets", params={"limit": 10}, timeout=10
    )
    assert resp.status_code == HTTPStatus.OK


@responses.activate
def test_add_openapi_to_responses_skips_invalid() -> None:
    """Add_openapi_to_responses skips non-dict path items and non-HTTP methods."""
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
    add_openapi_to_responses(spec=spec, base_url="https://api.example.com")
    resp = requests.get(url="https://api.example.com/valid", timeout=10)
    assert resp.status_code == HTTPStatus.OK
