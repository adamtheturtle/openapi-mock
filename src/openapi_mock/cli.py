"""CLI for serving an OpenAPI spec as a mock API."""

from __future__ import annotations

import argparse
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from uvicorn import run as uvicorn_run

from openapi_mock import load_spec


def _make_handler() -> object:
    """Create an async handler that returns empty JSON."""

    async def handler(request: object) -> JSONResponse:
        return JSONResponse({})

    return handler


def _create_routes(spec: dict) -> list[Route]:
    """Create Starlette routes from OpenAPI spec paths."""
    paths: dict = spec.get("paths", {}) or {}
    route_list: list[Route] = []

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(operation, dict):
                continue

            route_list.append(Route(path, _make_handler(), methods=[method.upper()]))

    return route_list


def serve(spec_path: str | Path, port: int = 8000, host: str = "127.0.0.1") -> None:
    """Serve the OpenAPI spec as a mock API."""
    spec = load_spec(spec_path)
    routes = _create_routes(spec)
    app = Starlette(routes=routes)
    uvicorn_run(app, host=host, port=port)


def main() -> None:
    """Entry point for the openapi-mock CLI."""
    parser = argparse.ArgumentParser(description="Serve an OpenAPI spec as a mock API")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Serve spec as mock API")
    serve_parser.add_argument(
        "spec",
        type=Path,
        help="Path to OpenAPI spec file (.json, .yaml, .yml)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to serve on (default: 8000)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    # Only "serve" is supported; subparsers required=True ensures we have a command
    serve(args.spec, port=args.port, host=args.host)
