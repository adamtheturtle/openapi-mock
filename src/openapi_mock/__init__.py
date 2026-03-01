"""Package for serving an OpenAPI spec as a mock with respx or responses."""

import json
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import httpx
import respx
import yaml
from beartype import beartype


def _generate_from_schema(schema: dict[str, Any]) -> Any:
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
                result[prop_name] = _generate_from_schema(prop_schema)
        return result
    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [_generate_from_schema(items)]
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


def _get_example_from_content(json_content: dict[str, Any]) -> Any | None:
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


def _get_response_body(operation: dict[str, Any]) -> tuple[int | HTTPStatus, Any]:
    """
    Get (status_code, json_body) for the best response in an operation.

    Prefers 200, then 201, then first 2xx, then first response.
    Uses example if present, else generates from schema.
    """
    raw_responses = operation.get("responses") or {}
    if not raw_responses:
        return HTTPStatus.OK, {}

    # Normalize keys to str (YAML may produce int keys for unquoted 200:, 201:, etc.)
    responses: dict[str, Any] = {str(k): v for k, v in raw_responses.items()}

    # Prefer 200, then 201, then first 2xx, then first
    for preferred in (str(HTTPStatus.OK.value), str(HTTPStatus.CREATED.value)):
        if preferred in responses:
            status_key = preferred
            break
    else:
        for key in responses:
            if (
                key.isdigit()
                and HTTPStatus.OK.value <= int(key) < HTTPStatus.MULTIPLE_CHOICES.value
            ):
                status_key = key
                break
        else:
            status_key = next(iter(responses), str(HTTPStatus.OK.value))

    default_status: int | HTTPStatus = HTTPStatus.OK
    if status_key.isdigit():
        code = int(status_key)
        try:
            default_status = HTTPStatus(code)
        except ValueError:
            default_status = code

    response = responses.get(status_key, {})
    if not isinstance(response, dict):
        return default_status, {}

    content = response.get("content", {}) or {}
    json_content = content.get("application/json") or {}
    if not isinstance(json_content, dict):
        return default_status, {}

    example = _get_example_from_content(json_content)
    if example is not None:
        return default_status, example
    schema = json_content.get("schema")
    if isinstance(schema, dict):
        return default_status, _generate_from_schema(schema)
    return default_status, {}


@beartype
def load_spec(path: str | Path) -> dict[str, Any]:
    """
    Load an OpenAPI spec from a file (JSON or YAML).

    :param path: Path to the spec file (``.json`` or ``.yaml``/``.yml``).
    :return: OpenAPI spec as a dict.
    """
    path = Path(path)
    text = path.read_text()
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in (".yaml", ".yml"):
        result = yaml.safe_load(text)
        if result is None:
            raise ValueError("Empty or null YAML spec")
        return result
    msg = f"Unsupported format: {suffix}. Use .json, .yaml, or .yml"
    raise ValueError(msg)


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

            status_code, json_body = _get_response_body(operation)
            mock_obj.route(
                method=method.upper(),
                path=path,
            ).mock(return_value=httpx.Response(status_code, json=json_body))


def _path_to_url_pattern(base_url: str, path: str) -> str:
    """Convert OpenAPI path to full URL regex pattern for path param matching."""
    base = base_url.rstrip("/")
    path_part = path if path.startswith("/") else f"/{path}"
    # Replace {param} with [^/]+ to match any path segment
    pattern = re.sub(r"\{[^}]+}", "[^/]+", path_part)
    return f"{re.escape(base)}{pattern}"


@beartype
def add_openapi_to_responses(
    *,
    spec: dict[str, Any],
    base_url: str,
) -> None:
    """
    Add mock routes from an OpenAPI spec to the responses library.

    Use with ``@responses.activate`` or the ``responses`` pytest fixture.
    Requires ``pip install openapi-mock[responses]``.

    :param spec: OpenAPI 3.0 or 3.1 spec as a dict (from JSON or YAML).
    :param base_url: Base URL for all routes (e.g. ``https://api.example.com``).
    """
    import responses as responses_mod

    paths: dict[str, Any] = spec.get("paths", {}) or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in cast(dict[str, Any], path_item).items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(operation, dict):
                continue

            status_code, json_body = _get_response_body(operation)
            code = int(status_code) if isinstance(status_code, HTTPStatus) else status_code
            url_pattern = _path_to_url_pattern(base_url, path)
            responses_mod.add(
                method=method.upper(),
                url=re.compile(f"^{url_pattern}$"),
                json=json_body,
                status=code,
            )
