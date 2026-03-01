"""Tests for CLI serve command."""

import sys
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from openapi_mock.cli import _create_routes, main, serve


def test_main_serve_calls_serve(tmp_path: Path) -> None:
    """main serve parses args and calls serve."""
    spec_path = tmp_path / "spec.json"
    spec_path.write_text('{"openapi": "3.0.0", "paths": {}}')

    with patch("openapi_mock.cli.serve") as mock_serve:
        old_argv = sys.argv
        sys.argv = ["openapi-mock", "serve", str(spec_path)]
        try:
            main()
        finally:
            sys.argv = old_argv
        mock_serve.assert_called_once_with(spec_path, port=8000, host="127.0.0.1")


def test_main_serve_with_port_and_host(tmp_path: Path) -> None:
    """main serve passes --port and --host to serve."""
    spec_path = tmp_path / "spec.json"
    spec_path.write_text('{"openapi": "3.0.0", "paths": {}}')

    with patch("openapi_mock.cli.serve") as mock_serve:
        old_argv = sys.argv
        sys.argv = [
            "openapi-mock",
            "serve",
            str(spec_path),
            "--port",
            "9000",
            "--host",
            "0.0.0.0",
        ]
        try:
            main()
        finally:
            sys.argv = old_argv
        mock_serve.assert_called_once_with(spec_path, port=9000, host="0.0.0.0")


def test_create_routes_from_spec() -> None:
    """Routes are created from OpenAPI paths."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {"description": "OK"}}},
                "post": {"responses": {"201": {"description": "Created"}}},
            },
        },
    }
    routes = _create_routes(spec)
    assert len(routes) == 2
    paths = [r.path for r in routes]
    assert "/pets" in paths


def test_create_routes_skips_non_http_methods() -> None:
    """Non-HTTP methods are skipped."""
    spec = {"paths": {"/pets": {"parameters": []}}}
    routes = _create_routes(spec)
    assert len(routes) == 0


def test_create_routes_skips_non_dict_path_item() -> None:
    """Non-dict path items are skipped."""
    spec = {"paths": {"/pets": "invalid"}}
    routes = _create_routes(spec)
    assert len(routes) == 0


def test_create_routes_skips_non_dict_operation() -> None:
    """Non-dict operations are skipped."""
    spec = {"paths": {"/pets": {"get": "invalid"}}}
    routes = _create_routes(spec)
    assert len(routes) == 0


def test_serve_returns_json_response() -> None:
    """Served endpoints return empty JSON."""
    from starlette.testclient import TestClient

    from openapi_mock.cli import _create_routes
    from starlette.applications import Starlette

    spec = {
        "openapi": "3.0.0",
        "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    routes = _create_routes(spec)
    app = Starlette(routes=routes)

    client = TestClient(app)
    response = client.get("/pets")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_serve_starts_server(tmp_path: Path) -> None:
    """Serve starts uvicorn with the mock app."""
    spec_path = tmp_path / "spec.json"
    spec_path.write_text('{"openapi": "3.0.0", "paths": {"/": {"get": {}}}}')

    with patch("openapi_mock.cli.uvicorn_run") as mock_run:
        serve(spec_path, port=9999, host="127.0.0.1")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[1]["port"] == 9999
        assert call_args[1]["host"] == "127.0.0.1"
