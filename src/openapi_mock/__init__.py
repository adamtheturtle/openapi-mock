"""Package for serving an OpenAPI spec as a mock with respx."""

from typing import Any, cast

import httpx
import respx


def add_openapi_to_respx(
    *,
    mock_obj: respx.MockRouter | respx.Router,
    spec: dict[str, Any],
    base_url: str,
) -> None:
    """
    Add mock routes from an OpenAPI spec to a respx mock/router.

    :param mock_obj: The respx MockRouter or Router to add routes to.
    :param spec: OpenAPI 3.x spec as a dict (from JSON or YAML).
    :param base_url: Base URL for all routes. Must match ``respx.mock()``.
    """
    paths: dict[str, Any] = spec.get("paths", {}) or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in cast(dict[str, Any], path_item).items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(operation, dict):
                continue

            mock_obj.route(
                method=method.upper(),
                path=path,
            ).mock(return_value=httpx.Response(200, json={}))
