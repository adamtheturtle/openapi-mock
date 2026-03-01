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
        add_openapi_to_respx(m, spec, base_url="https://api.example.com")
        response = httpx.get("https://api.example.com/pets")
    assert response.status_code == 200
    assert response.json() == {}
