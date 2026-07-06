"""Module for representing the ESI OpenAPI schema and its operations in a structured way."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Self, cast

from esi_link.helpers.resolve_json_ref import resolve_internal_refs


@dataclass(slots=True, kw_only=True, frozen=True)
class SchemaOperation:
    """Represents an operation defined in the ESI OpenAPI schema.

    This class is used to store the details of an operation, including the path, method,
    operation ID, and the full operation schema. This allows for easy access to the
    details of each operation when generating documentation or validating requests.

    A flattened version of the path, method, and operation object from the OpenAPI schema.
    "paths":<path>:<method>:<operation_schema> from the OpenAPI schema.
    """

    path: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    operation_schema: dict[str, Any]

    @property
    def operation_id(self) -> str:
        """Extract the operation ID from the operation object."""
        return self.operation_schema.get("operationId", "")

    @property
    def tags(self) -> list[str]:
        """Extract the tags from the operation object, if present."""
        return [tag for tag in self.operation_schema.get("tags", [])]

    @property
    def description(self) -> str:
        """Extract the description from the operation object, if present."""
        return self.operation_schema.get("description", "")

    @property
    def path_and_query_parameters(self) -> list[dict[str, Any]]:
        """Extract all parameters from the operation object, if present."""
        return [
            deepcopy(param)
            for param in self.operation_schema.get("parameters", [])
            if param.get("in") in {"path", "query"}
        ]

    @property
    def path_parameters(self) -> list[dict[str, Any]]:
        """Extract the path parameters from the operation object, if present."""
        return [
            deepcopy(param)
            for param in self.operation_schema.get("parameters", [])
            if param.get("in") == "path"
        ]

    @property
    def query_parameters(self) -> list[dict[str, Any]]:
        """Extract the query parameters from the operation object, if present."""
        return [
            deepcopy(param)
            for param in self.operation_schema.get("parameters", [])
            if param.get("in") == "query"
        ]

    @property
    def header_params(self) -> list[dict[str, Any]]:
        """Extract the header parameters from the operation object, if present."""
        return [
            deepcopy(param)
            for param in self.operation_schema.get("parameters", [])
            if param.get("in") == "header"
        ]

    @property
    def responses(self) -> dict[str, Any]:
        """Extract the response schema from the operation object, if present."""
        success_responses = (
            self.operation_schema.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        return deepcopy(success_responses)

    @property
    def request_body(self) -> dict[str, Any] | None:
        """Extract the request body from the operation object, if present."""
        return deepcopy(self.operation_schema.get("requestBody"))

    @property
    def is_authentication_required(self) -> bool:
        """Determine if the operation requires authentication based on the presence of security requirements."""
        return "security" in self.operation_schema and bool(
            self.operation_schema["security"]
        )

    @property
    def is_paged(self) -> bool:
        """Determine if the operation is paged based on the presence of pagination-related parameters."""
        for param in self.query_parameters:
            if param.get("name") in {"page"}:
                return True
        return False

    @property
    def is_cached(self) -> bool:
        """Determine if the operation is cacheable."""
        if self.method in {"GET", "get"}:
            return True
        return False

    @property
    def summary(self) -> str | None:
        """Extract the summary from the operation object, if present."""
        return self.operation_schema.get("summary")

    @property
    def x_compatibility_date(self) -> str:
        """Extract the x-compatibility-date from the operation object, if present."""
        value = self.operation_schema.get("x-compatibility-date")
        if value is None:
            raise ValueError(
                f"Operation {self.operation_id} is missing required x-compatibility-date field."
            )
        return value

    @property
    def x_values(self) -> list[dict[str, Any]]:
        """Extract the x-values from the operation object, if present."""
        x_list: list[dict[str, Any]] = []
        for key, value in self.operation_schema.items():
            if key.startswith("x-"):
                x_list.append({key: deepcopy(value)})
        return x_list


@dataclass(slots=True, kw_only=True, frozen=True)
class EsiSchema:
    """Represents the ESI OpenAPI schema and its associated metadata.

    For ease of access to the details of the schema.
    """

    dereferenced_schema: dict[str, Any]

    def __post_init__(self) -> None:
        """Ensure that the schema is valid."""
        if "openapi" not in self.dereferenced_schema:
            raise ValueError("Invalid schema: missing 'openapi' field")

    @classmethod
    def from_raw_schema(cls, raw_schema: dict[str, Any]) -> Self:
        """Factory method to create an EsiSchema instance from a raw OpenAPI schema.

        This method will resolve all internal JSON references in the schema, so that
        the resulting EsiSchema instance contains a fully dereferenced schema for easy
        access to all the details of the operations defined in the schema.

        Args:
            raw_schema: The raw OpenAPI schema as a dictionary.

        Returns:
            An instance of EsiSchema with the dereferenced schema.
        """
        dereferenced_schema = resolve_internal_refs(raw_schema, raw_schema)
        return cls(dereferenced_schema=dereferenced_schema)

    @property
    def operation_ids(self) -> set[str]:
        """Extract the set of operation IDs from the schema."""
        operation_ids: set[str] = set()
        paths = self.dereferenced_schema.get("paths", {})
        for _path, methods in paths.items():
            for _method, operation in methods.items():
                operation_id = operation.get("operationId")
                if operation_id:
                    operation_ids.add(operation_id)
        return operation_ids

    @property
    def operations(self) -> dict[str, SchemaOperation]:
        """Extract the operations from the schema and return them as a dictionary mapping operation IDs to SchemaOperation instances."""
        operations: dict[str, SchemaOperation] = {}
        operation_ids = self.operation_ids
        for operation_id in operation_ids:
            operation = self.get_operation_by_id(operation_id)
            if operation:
                operations[operation_id] = operation
        return operations

    def get_operation_by_id(self, operation_id: str) -> SchemaOperation | None:
        """Get a SchemaOperation by its operation ID."""
        paths = self.dereferenced_schema.get("paths", {})
        for path, methods in paths.items():
            for method, operation in methods.items():
                if operation.get("operationId") == operation_id:
                    return SchemaOperation(
                        path=path,
                        method=method.upper(),
                        operation_schema=deepcopy(operation),
                    )
        return None

    @property
    def operation_id_by_tag(self) -> dict[str, list[str]]:
        """Extract a mapping of tags to operation IDs from the schema."""
        tag_mapping: dict[str, list[str]] = {}
        paths = self.dereferenced_schema.get("paths", {})
        for _path, methods in paths.items():
            for _method, operation in methods.items():
                operation_id = operation.get("operationId")
                tags = operation.get("tags", [])
                if not tags:
                    tags = ["untagged"]
                for tag in tags:
                    if tag not in tag_mapping:
                        tag_mapping[tag] = []
                    if operation_id:
                        tag_mapping[tag].append(operation_id)
        # sort the tags alphabetically, and the operation IDs within each tag alphabetically as well
        tag_mapping = {
            tag: sorted(operation_ids)
            for tag, operation_ids in sorted(tag_mapping.items())
        }
        return tag_mapping

    @property
    def compatibility_date(self) -> str:
        """Get the compatibility date of the ESI schema from the info section."""
        return self.version

    @property
    def version(self) -> str:
        """Get the version of the ESI schema based on the compatibility date."""
        version = cast(str, self.dereferenced_schema["info"]["version"])
        return version

    @property
    def base_url(self) -> str:
        """Get the base URL for the ESI API from the servers section of the schema."""
        return self.dereferenced_schema["servers"][0]["url"]

    @property
    def content_languages(self) -> set[str]:
        """Get the content languages supported by the ESI API from the schema."""
        return set(
            self.dereferenced_schema.get("components", {})
            .get("headers", {})
            .get("ContentLanguage", {})
            .get("schema", {})
            .get("enum", [])
        )
