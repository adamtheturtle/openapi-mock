"""Package for serving an OpenAPI spec as a mock with respx or responses."""

import re
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any, cast

import httpx
import respx
import responses
from beartype import beartype
from openapi_pydantic import (
    Components,
    Example,
    MediaType,
    OpenAPI,
    Operation,
    Reference,
)
from openapi_pydantic import Response as OAResponse
from openapi_pydantic import Schema
from openapi_pydantic.v3.v3_1.datatype import DataType
from pydantic import ValidationError

_HTTP_METHODS = ("get", "post", "put", "delete", "patch")

# Keys that are valid on a PathItem besides HTTP methods.
_PATH_ITEM_NON_METHOD_KEYS = frozenset(
    {
        "summary",
        "description",
        "servers",
        "parameters",
        "$ref",
    }
)


@beartype
def _preprocess_schema(*, schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a schema dict, filtering non-dict property schemas."""
    result = dict(schema)
    props = result.get("properties")
    if isinstance(props, dict):
        typed_props = cast(dict[str, Any], props)
        result["properties"] = {
            k: _preprocess_schema(schema=cast(dict[str, Any], v))
            for k, v in typed_props.items()
            if isinstance(v, dict)
        }
    items = result.get("items")
    if isinstance(items, dict):
        result["items"] = _preprocess_schema(schema=cast(dict[str, Any], items))
    return result


@beartype
def _preprocess_content(*, content: dict[str, Any]) -> dict[str, Any]:
    """Normalize a content dict, filtering non-dict media types."""
    result: dict[str, Any] = {}
    for media_type_key, media_type_val in content.items():
        if not isinstance(media_type_val, dict):
            continue
        media_copy: dict[str, Any] = dict(cast(dict[str, Any], media_type_val))
        schema = media_copy.get("schema")
        if isinstance(schema, dict):
            media_copy["schema"] = _preprocess_schema(
                schema=cast(dict[str, Any], schema),
            )
        elif schema is not None:
            # Boolean schemas (True/False) and other non-dict values are
            # not supported by openapi-pydantic. Remove them.
            media_copy.pop("schema", None)
        result[media_type_key] = media_copy
    return result


@beartype
def _preprocess_responses(
    *, raw_responses: dict[str | int, Any],
) -> dict[str, Any]:
    """Normalize response dicts: int keys to str, add description, filter invalid."""
    new_responses: dict[str, Any] = {}
    for status_key, resp_val in raw_responses.items():
        str_key = f"{status_key}"
        if not isinstance(resp_val, dict):
            continue
        resp_copy: dict[str, Any] = dict(cast(dict[str, Any], resp_val))
        if "description" not in resp_copy:
            resp_copy["description"] = ""
        content = resp_copy.get("content")
        if isinstance(content, dict):
            resp_copy["content"] = _preprocess_content(
                content=cast(dict[str, Any], content),
            )
        new_responses[str_key] = resp_copy
    return new_responses


@beartype
def _preprocess_spec(*, spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw spec dict for openapi-pydantic parsing.

    Converts YAML int keys to str, adds missing required fields,
    and filters out non-dict values where dicts are expected.
    """
    result = dict(spec)

    if "info" not in result:
        result["info"] = {"title": "", "version": ""}
    # The v3.1 models accept only "3.1.0" or "3.1.1". Since v3.1 is a
    # superset of v3.0, we always parse as 3.1 regardless of the original
    # version. The version string is not used by our mocking logic.
    result["openapi"] = "3.1.0"

    paths = result.get("paths")
    if not isinstance(paths, dict):
        return result

    typed_paths = cast(dict[str, Any], paths)
    new_paths: dict[str, Any] = {}
    for path_key, path_item in typed_paths.items():
        if not isinstance(path_item, dict):
            continue
        typed_path_item = cast(dict[str, Any], path_item)
        new_path_item: dict[str, Any] = {}
        for method_key, value in typed_path_item.items():
            if method_key.lower() in _HTTP_METHODS:
                if not isinstance(value, dict):
                    continue
                op_copy: dict[str, Any] = dict(cast(dict[str, Any], value))
                raw_resp = op_copy.get("responses")
                if isinstance(raw_resp, dict):
                    op_copy["responses"] = _preprocess_responses(
                        raw_responses=cast(dict[str | int, Any], raw_resp),
                    )
                new_path_item[method_key] = op_copy
            elif method_key in _PATH_ITEM_NON_METHOD_KEYS:
                new_path_item[method_key] = value
        new_paths[path_key] = new_path_item
    result["paths"] = new_paths
    return result


@beartype
def _parse_spec(*, spec: dict[str, Any]) -> OpenAPI | None:
    """Parse a raw spec dict into an OpenAPI model.

    Returns None on failure.
    """
    preprocessed = _preprocess_spec(spec=spec)
    try:
        return OpenAPI.model_validate(obj=preprocessed)
    except ValidationError:
        return None


@beartype
def _resolve_schema_ref(
    *,
    ref_or_obj: Schema | Reference,
    components: Components | None,
) -> Schema | None:
    """Resolve a Schema or Reference to a Schema.

    Returns None if unresolvable.
    """
    if not isinstance(ref_or_obj, Reference):
        return ref_or_obj
    if components is None or components.schemas is None:
        return None
    prefix = "#/components/schemas/"
    if not ref_or_obj.ref.startswith(prefix):
        return None
    name = ref_or_obj.ref[len(prefix) :]
    return components.schemas.get(name)


@beartype
def _resolve_response_ref(
    *,
    ref_or_obj: OAResponse | Reference,
    components: Components | None,
) -> OAResponse | None:
    """Resolve a Response or Reference to a Response.

    Returns None if unresolvable.
    """
    if not isinstance(ref_or_obj, Reference):
        return ref_or_obj
    if components is None or components.responses is None:
        return None
    prefix = "#/components/responses/"
    if not ref_or_obj.ref.startswith(prefix):
        return None
    name = ref_or_obj.ref[len(prefix) :]
    target = components.responses.get(name)
    if isinstance(target, Reference):
        return None
    return target


@beartype
def _resolve_example_ref(
    *,
    ref_or_obj: Example | Reference,
    components: Components | None,
) -> Example | None:
    """Resolve an Example or Reference to an Example.

    Returns None if unresolvable.
    """
    if not isinstance(ref_or_obj, Reference):
        return ref_or_obj
    if components is None or components.examples is None:
        return None
    prefix = "#/components/examples/"
    if not ref_or_obj.ref.startswith(prefix):
        return None
    name = ref_or_obj.ref[len(prefix) :]
    target = components.examples.get(name)
    if isinstance(target, Reference):
        return None
    return target


@beartype
def _generate_from_schema(
    *,
    schema: Schema,
    components: Components | None,
) -> Any:
    """Generate mock JSON from a Schema model.

    Handles type, properties, items. Supports type as array (OpenAPI 3.1).
    Resolves $ref.
    """
    schema_type = schema.type
    # OpenAPI 3.1 / JSON Schema 2020-12: type can be array, e.g. ["string", "null"]
    if isinstance(schema_type, list) and schema_type:
        schema_type = next(
            (t for t in schema_type if t != DataType.NULL),
            schema_type[0],
        )
    if schema_type == DataType.OBJECT:
        result: dict[str, Any] = {}
        for prop_name, prop_schema_or_ref in (schema.properties or {}).items():
            resolved = _resolve_schema_ref(
                ref_or_obj=prop_schema_or_ref,
                components=components,
            )
            if resolved is not None:
                result[prop_name] = _generate_from_schema(
                    schema=resolved,
                    components=components,
                )
        return result
    if schema_type == DataType.ARRAY:
        items = schema.items
        if items is not None:
            resolved = _resolve_schema_ref(
                ref_or_obj=items,
                components=components,
            )
            if resolved is not None:
                return [
                    _generate_from_schema(
                        schema=resolved,
                        components=components,
                    )
                ]
        return []
    if schema_type == DataType.STRING:
        return ""
    if schema_type in (DataType.NUMBER, DataType.INTEGER):
        return 0
    if schema_type == DataType.BOOLEAN:
        return False
    if schema_type == DataType.NULL:
        return None
    return {}


@beartype
def _get_example_from_content(
    *,
    media_type: MediaType,
    components: Components | None,
) -> Any | None:
    """Get example value from a MediaType.

    Checks OpenAPI 3.0 example then 3.1 examples. Returns None if not found.
    """
    if media_type.example is not None:
        return media_type.example
    examples = media_type.examples
    if not examples:
        return None
    first_ex_or_ref = next(iter(examples.values()))
    resolved = _resolve_example_ref(
        ref_or_obj=first_ex_or_ref,
        components=components,
    )
    if resolved is not None and resolved.value is not None:
        return resolved.value
    return None


@beartype
def _get_response_body(
    *,
    operation: Operation,
    components: Components | None,
) -> tuple[int | HTTPStatus, Any]:
    """Get (status_code, json_body) for the best response in an operation.

    Prefers 200, then 201, then first 2xx, then first response.
    Uses example if present, else generates from schema.
    """
    raw_responses = operation.responses or {}
    if not raw_responses:
        return HTTPStatus.OK, {}

    # Prefer 200, then 201, then first 2xx, then first
    for preferred in (f"{HTTPStatus.OK.value}", f"{HTTPStatus.CREATED.value}"):
        if preferred in raw_responses:
            status_key = preferred
            break
    else:
        for key in raw_responses:
            if (
                key.isdigit()
                and HTTPStatus.OK.value
                <= int(key)
                < HTTPStatus.MULTIPLE_CHOICES.value
            ):
                status_key = key
                break
        else:
            status_key = next(iter(raw_responses), f"{HTTPStatus.OK.value}")

    default_status: int | HTTPStatus = HTTPStatus.OK
    if status_key.isdigit():
        code = int(status_key)
        try:
            default_status = HTTPStatus(value=code)
        except ValueError:
            default_status = code

    response_or_ref = raw_responses[status_key]
    response = _resolve_response_ref(
        ref_or_obj=response_or_ref,
        components=components,
    )
    if response is None:
        return default_status, {}

    content = response.content or {}
    media = content.get("application/json")
    if media is None:
        return default_status, {}

    example = _get_example_from_content(media_type=media, components=components)
    if example is not None:
        return default_status, example

    schema_or_ref = media.media_type_schema
    if schema_or_ref is not None:
        resolved = _resolve_schema_ref(
            ref_or_obj=schema_or_ref,
            components=components,
        )
        if resolved is not None:
            return default_status, _generate_from_schema(
                schema=resolved,
                components=components,
            )
    return default_status, {}


@beartype
def _iter_operations(
    *,
    parsed: OpenAPI,
) -> Iterator[tuple[str, str, Operation]]:
    """Yield (path, method, Operation) from a parsed OpenAPI model."""
    paths = parsed.paths or {}
    for path, path_item in paths.items():
        for method in _HTTP_METHODS:
            operation: Operation | None = getattr(path_item, method, None)
            if operation is not None:
                yield path, method, operation


@beartype
def add_openapi_to_respx(
    *,
    mock_obj: respx.MockRouter | respx.Router,
    spec: dict[str, Any],
    base_url: str,
) -> None:
    """Add mock routes from an OpenAPI spec to a respx mock/router.

    :param mock_obj: The respx MockRouter or Router to add routes to.
    :param spec: OpenAPI 3.0 or 3.1 spec as a dict (from JSON or YAML).
    :param base_url: Base URL for all routes. Must match ``respx.mock()``.
    """
    parsed = _parse_spec(spec=spec)
    if parsed is None:
        return

    components = parsed.components

    for path, method, operation in _iter_operations(parsed=parsed):
        status_code, json_body = _get_response_body(
            operation=operation,
            components=components,
        )
        if "{" in path:
            path_pattern = _path_to_pattern(path=path)
            mock_obj.route(
                method=method.upper(),
                path__regex=re.compile(pattern=f"^{path_pattern}$"),
            ).mock(
                return_value=httpx.Response(
                    status_code=status_code, json=json_body
                )
            )
        else:
            mock_obj.route(
                method=method.upper(),
                path=path,
            ).mock(
                return_value=httpx.Response(
                    status_code=status_code, json=json_body
                )
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
    """Add mock routes from an OpenAPI spec to the responses library.

    Use with ``@responses.activate`` or the ``responses`` pytest fixture.
    When using ``with responses.RequestsMock() as rsps``, pass ``mock=rsps``.

    :param spec: OpenAPI 3.0 or 3.1 spec as a dict (from JSON or YAML).
    :param base_url: Base URL for all routes (e.g. ``https://api.example.com``).
    :param mock: Optional RequestsMock instance. If given, routes are added to
        this mock instead of the default. Use when using ``responses.RequestsMock``
        as a context manager.
    """
    parsed = _parse_spec(spec=spec)
    if parsed is None:
        return

    add_fn = (mock or responses).add
    components = parsed.components

    for path, method, operation in _iter_operations(parsed=parsed):
        status_code, json_body = _get_response_body(
            operation=operation,
            components=components,
        )
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
