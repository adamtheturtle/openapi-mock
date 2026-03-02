"""Package for serving an OpenAPI spec as a mock with respx or responses."""

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import httpx
import respx
import responses
from beartype import beartype
from prance import ResolvingParser  # type: ignore[import-untyped]


@beartype
def _generate_from_schema(*, schema: dict[str, Any]) -> Any:
    """
    Generate mock JSON from a JSON Schema (OpenAPI 3.0/3.1 schema subset).

    Handles type, properties, items. Supports type as array (OpenAPI 3.1).
    Does not resolve $ref.
    """
    schema_type = schema.get("type")
    # OpenAPI 3.1 / JSON Schema 2020-12: type can be array, e.g. ["string", "null"]
    if isinstance(schema_type, list) and schema_type:
        schema_type = next((t for t in schema_type if t != "null"), schema_type[0])
    if schema_type == "object":
        result: dict[str, Any] = {}
        for prop_name, prop_schema in (schema.get("properties") or {}).items():
            if isinstance(prop_schema, dict):
                result[prop_name] = _generate_from_schema(schema=prop_schema)
        return result
    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [_generate_from_schema(schema=items)]
        return []
    if schema_type == "string":
        return ""
    if schema_type in ("number", "integer"):
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    return {}


@beartype
def _get_example_from_content(*, json_content: dict[str, Any]) -> Any | None:
    """Get example value from OpenAPI 3.0 example or 3.1 examples. Returns None if not found."""
    if "example" in json_content:
        return json_content["example"]
    examples = json_content.get("examples")
    if isinstance(examples, dict):
        for ex in examples.values():
            if isinstance(ex, dict) and "value" in ex:
                return ex["value"]
            break
    return None


@beartype
def _get_response_body(*, operation: dict[str, Any]) -> tuple[int | HTTPStatus, Any]:
    """
    Get (status_code, json_body) for the best response in an operation.

    Prefers 200, then 201, then first 2xx, then first response.
    Uses example if present, else generates from schema.
    """
    raw_responses = operation.get("responses") or {}
    if not raw_responses:
        return HTTPStatus.OK, {}

    # Normalize keys to str (YAML may produce int keys for unquoted 200:, 201:, etc.)
    status_responses: dict[str, Any] = {f"{k}": v for k, v in raw_responses.items()}

    # Prefer 200, then 201, then first 2xx, then first
    for preferred in (f"{HTTPStatus.OK.value}", f"{HTTPStatus.CREATED.value}"):
        if preferred in status_responses:
            status_key = preferred
            break
    else:
        for key in status_responses:
            if (
                key.isdigit()
                and HTTPStatus.OK.value <= int(key) < HTTPStatus.MULTIPLE_CHOICES.value
            ):
                status_key = key
                break
        else:
            status_key = next(iter(status_responses), f"{HTTPStatus.OK.value}")

    default_status: int | HTTPStatus = HTTPStatus.OK
    if status_key.isdigit():
        code = int(status_key)
        try:
            default_status = HTTPStatus(value=code)
        except ValueError:
            default_status = code

    response = status_responses.get(status_key, {})
    if not isinstance(response, dict):
        return default_status, {}

    content = response.get("content", {}) or {}
    json_content = content.get("application/json") or {}
    if not isinstance(json_content, dict):
        return default_status, {}

    example = _get_example_from_content(json_content=json_content)
    if example is not None:
        return default_status, example
    schema = json_content.get("schema")
    if isinstance(schema, dict):
        return default_status, _generate_from_schema(schema=schema)
    return default_status, {}


@beartype
def load_spec(path: str | Path) -> dict[str, Any]:
    """
    Load an OpenAPI spec from a file (JSON or YAML).

    Uses prance for parsing and resolving ``$ref`` references. Supports
    OpenAPI 2.0 (Swagger), 3.0, and 3.1 specifications.

    :param path: Path to the spec file (``.json`` or ``.yaml``/``.yml``).
    :return: OpenAPI spec as a dict, with ``$ref`` references resolved.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    parser = ResolvingParser(
        url=str(object=path.resolve()), backend="openapi-spec-validator"
    )
    return cast(dict[str, Any], parser.specification)


@beartype
def add_openapi_to_respx(
    *,
    mock_obj: respx.MockRouter | respx.Router,
    spec: dict[str, Any],
    base_url: str,
) -> None:
    """
    Add mock routes from an OpenAPI spec to a respx mock/router.

    :param mock_obj: The respx MockRouter or Router to add routes to.
    :param spec: OpenAPI 3.0 or 3.1 spec as a dict (from JSON or YAML).
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

            status_code, json_body = _get_response_body(operation=operation)
            if "{" in path:
                path_pattern = _path_to_pattern(path=path)
                mock_obj.route(
                    method=method.upper(),
                    path__regex=re.compile(pattern=f"^{path_pattern}$"),
                ).mock(
                    return_value=httpx.Response(status_code=status_code, json=json_body)
                )
            else:
                mock_obj.route(
                    method=method.upper(),
                    path=path,
                ).mock(
                    return_value=httpx.Response(status_code=status_code, json=json_body)
                )


@beartype
def _path_to_pattern(*, path: str) -> str:
    """Convert OpenAPI path to path pattern (e.g. /pets/{id} -> /pets/[^/]+)."""
    path_part = path if path.startswith("/") else f"/{path}"
    segments = path_part.split(sep="/")
    pattern_parts = [
        "[^/]+"
        if re.match(pattern=r"^\{[^}]*\}$", string=seg)
        else re.escape(pattern=seg)
        for seg in segments
    ]
    return "/".join(pattern_parts)


@beartype
def _path_to_url_pattern(
    *,
    base_url: str,
    path: str,
) -> str:
    """Convert OpenAPI path to full URL regex pattern for path param matching."""
    base = base_url.rstrip("/")
    return f"{re.escape(pattern=base)}{_path_to_pattern(path=path)}"


@beartype
def add_openapi_to_responses(
    *,
    spec: dict[str, Any],
    base_url: str,
    mock: responses.RequestsMock | None = None,
) -> None:
    """
    Add mock routes from an OpenAPI spec to the responses library.

    Use with ``@responses.activate`` or the ``responses`` pytest fixture.
    When using ``with responses.RequestsMock() as rsps``, pass ``mock=rsps``.

    :param spec: OpenAPI 3.0 or 3.1 spec as a dict (from JSON or YAML).
    :param base_url: Base URL for all routes (e.g. ``https://api.example.com``).
    :param mock: Optional RequestsMock instance. If given, routes are added to
        this mock instead of the default. Use when using ``responses.RequestsMock``
        as a context manager.
    """
    add_fn = (mock or responses).add
    paths: dict[str, Any] = spec.get("paths", {}) or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in cast(dict[str, Any], path_item).items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(operation, dict):
                continue

            status_code, json_body = _get_response_body(operation=operation)
            code = (
                int(status_code) if isinstance(status_code, HTTPStatus) else status_code
            )
            url_pattern = _path_to_url_pattern(base_url=base_url, path=path)
            add_fn(
                method=method.upper(),
                url=re.compile(pattern=f"^{url_pattern}(?:\\?.*)?$"),
                json=json_body,
                status=code,
            )
