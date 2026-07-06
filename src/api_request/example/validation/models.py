"""Validation Models for ESI requests and request groups."""

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from pydantic import RootModel

from esi_link.actions.models import Action, GroupAction
from esi_link.request.models import Request
from esi_link.type_defs import Lang


@dataclass(slots=True, kw_only=True, frozen=True)
class ValidatedRequestAction:
    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(slots=True, kw_only=True, frozen=True)
class InvalidRequestAction:
    request_action: Action
    """The original request action that failed validation."""
    errors: tuple[str, ...]
    """A tuple of error messages describing the validation failures."""


@dataclass(slots=True, kw_only=True, frozen=True)
class ValidatedRequestGroupAction:
    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(slots=True, kw_only=True, frozen=True)
class InvalidRequestGroupAction:
    request_group_action: GroupAction
    """The original request group action that failed validation."""
    errors: tuple[str, ...]
    """A tuple of error messages describing the validation failures."""


@dataclass(slots=True, kw_only=True, frozen=True)
class ValidatedRequest:
    """Represents a validated ESI request, ready to be executed.

    The path, query, and json body parameters are duplicated from the original Request,
    but are now validated and ready to be used for the actual HTTP request to ESI. This
    allows for manipulation of the parameters during validation without affecting the
    original Request object, which can be useful for ensuring that the params used match
    the program's expectations. e.g. page is a valid query parameter for a paged operation,
    but the program may want to set it to 1 if it's not provided in the original Request,
    and this way the original Request remains unchanged, while the ValidatedRequest has
    the page parameter set to 1 for use in the actual HTTP request to ESI.

    Additional fields are added to capture required info from the schema for the request,
    such as the path URL template, HTTP method, and whether the request is paged or cacheable.
    This allows for easy access to this information during the execution of the request,
    without needing to refer back to the original Request or the ESI schema.

    """

    request_id: UUID
    """The unique identifier for the request. This is used to link the request to various 
        objects during the request lifecycle."""
    operation_id: str = "NOT_SET"
    """The operation ID of the request, corresponding to the operationId in the ESI OpenAPI 
        schema."""
    compatibility_date: str = ""
    """compatibility date for the request. If not provided by Request, the latest schema 
        compatibility date will be used."""
    x_compatibility_date: str = ""
    """The X-Compatibility-Date header value for the request. This is used to version 
        the cache key for a particular route, so that when the schema changes and the 
        x_compatibility_date is updated, the cache keys will also be updated, preventing 
        stale cached responses from being used."""
    path_parameters: dict[str, str | int | float] = field(
        default_factory=dict[str, str | int | float]
    )
    """The path parameters for the request, if applicable. This is used to fill in the 
        path parameters in the URL template."""
    query_parameters: dict[str, str | int | float] = field(
        default_factory=dict[str, str | int | float]
    )
    """The query parameters for the request, if applicable. This is used to fill in the 
        query parameters in the URL template."""
    authorization_id: int | None = None
    """The Character ID to use for authentication, if applicable."""
    language: Lang = "en"
    """The language to use for the request, if applicable. This is used to set the 
        Accept-Language header in the request."""
    json_body: Any | None = None
    """The JSON body of the request, if applicable. This is used for POST, PUT, PATCH 
        requests."""
    actions: list[ValidatedRequestAction] = field(
        default_factory=list[ValidatedRequestAction]
    )

    # These fields are added to capture required info from the schema for the request,
    # such as the path URL template, HTTP method, and whether the request is paged or cacheable.
    path_url_template: str = ""
    """The URL template for the path."""
    method: Literal[
        "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "NOT_SET"
    ] = "NOT_SET"
    """The HTTP method for the request."""
    is_paged: bool = False
    """Whether the request is paged or not, based on the presence of pagination-related 
        parameters in the operation schema."""
    is_cached: bool = False
    """Whether the request is cacheable or not, based on the HTTP method of the operation."""
    is_authentication_required: bool = False
    """Whether the request requires authentication or not, based on the presence of 
        security requirements in the operation schema."""


@dataclass(slots=True, kw_only=True, frozen=True)
class InvalidRequest:
    request: Request
    """The original request that failed validation."""
    errors: tuple[str, ...]
    """A list of error messages describing the validation failures."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the failed request validation with the specified indentation."""
        root_model = InvalidRequestRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> InvalidRequest:
        """Parse the failed request validation from a JSON string."""
        value = InvalidRequestRoot.model_validate_json(json_str).root
        return value


InvalidRequestRoot = RootModel[InvalidRequest]
