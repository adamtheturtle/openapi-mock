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


def test_skips_non_dict_path_item() -> None:
    """Non-dict path items are skipped."""
    spec = {"paths": {"/pets": "invalid"}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(m, spec, base_url="https://api.example.com")
    # No route added, nothing to assert


def test_skips_non_http_methods() -> None:
    """Non-HTTP methods are skipped."""
    spec = {"paths": {"/pets": {"parameters": []}}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(m, spec, base_url="https://api.example.com")
    # No route added


def test_skips_non_dict_operation() -> None:
    """Non-dict operations are skipped."""
    spec = {"paths": {"/pets": {"get": "invalid"}}}
    with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
        add_openapi_to_respx(m, spec, base_url="https://api.example.com")
    # No route added
