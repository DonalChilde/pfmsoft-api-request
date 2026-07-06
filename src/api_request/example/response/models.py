"""This module defines the Response and ResponseGroup data models for representing ESI responses and groups of responses in the ESI Link system."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import RootModel

from esi_link.execution.models import HttpResponse
from esi_link.request.models import Request, RequestGroup
from esi_link.runtime.models import (
    FailedRuntimeResponse,
    InvalidRuntimeRequest,
    RuntimeGroupMetrics,
    RuntimeRequest,
    RuntimeRequestMetrics,
)
from esi_link.validation.models import (
    InvalidRequest,
    ValidatedRequest,
    ValidatedRequestGroupAction,
)


@dataclass(slots=True, kw_only=True, frozen=True)
class ResponseGroupAction:
    """Represents an action to be taken after receiving a group of responses."""

    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(slots=True, kw_only=True, frozen=True)
class Response:
    request_id: UUID
    http_response: HttpResponse
    metrics: RuntimeRequestMetrics = field(default_factory=RuntimeRequestMetrics)

    def to_string(self, indent: int) -> str:
        """Return a string representation of the response with the specified indentation."""
        root_model = ResponseRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> Response:
        """Parse the response from a JSON string."""
        value = ResponseRoot.model_validate_json(json_str).root
        return value


ResponseRoot = RootModel[Response]


@dataclass(slots=True, kw_only=True)
class FailedResponse:
    http_response: HttpResponse | None
    runtime_request: RuntimeRequest
    metrics: RuntimeRequestMetrics = field(default_factory=RuntimeRequestMetrics)
    failure_msg: str = ""


@dataclass(slots=True, kw_only=True, frozen=True)
class ResponseGroup:
    """Represents a group of responses that are related to each other, such as responses from requests that were part of the same RequestGroup."""

    request_group: RequestGroup
    """The original request group that this response group corresponds to."""
    # These fields are determined during validation.
    valid_requests: dict[UUID, ValidatedRequest] = field(
        default_factory=dict[UUID, ValidatedRequest]
    )
    invalid_requests: dict[UUID, InvalidRequest] = field(
        default_factory=dict[UUID, InvalidRequest]
    )
    """The requests that failed validation."""
    valid_actions: list[ValidatedRequestGroupAction] = field(
        default_factory=list[ValidatedRequestGroupAction]
    )
    invalid_actions: list[ValidatedRequestGroupAction] = field(
        default_factory=list[ValidatedRequestGroupAction]
    )

    # These fields are determined prior to executing the requests in the group.
    metrics: RuntimeGroupMetrics = field(default_factory=RuntimeGroupMetrics)
    runtime_requests: dict[UUID, RuntimeRequest] = field(
        default_factory=dict[UUID, RuntimeRequest]
    )
    """A mapping of request_id to RuntimeRequest for all requests in the group."""
    invalid_runtime_requests: dict[UUID, InvalidRuntimeRequest] = field(
        default_factory=dict[UUID, InvalidRuntimeRequest]
    )
    """The requests that failed the transition from Validated to Runtime."""
    # These fields are determined after the requests are executed
    responses: dict[UUID, Response] = field(default_factory=dict[UUID, Response])
    """A mapping of request_id to Response for all requests in the group."""
    failed_responses: dict[UUID, FailedResponse] = field(
        default_factory=dict[UUID, FailedResponse]
    )
    """The requests that failed during execution."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the ResponseGroup with the specified indentation."""
        root_model = ResponseGroupRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> ResponseGroup:
        """Parse the ResponseGroup from a JSON string."""
        value = ResponseGroupRoot.model_validate_json(json_str).root
        return value


ResponseGroupRoot = RootModel[ResponseGroup]


@dataclass(slots=True, kw_only=True, frozen=True)
class ResponseData:
    """Represents the data returned in a successful response to an ESI request.

    TODO this model could use some refinement.
    Expectations are that this is the data that the user is most interested in, and
    should be formatted in a way that is easy to understand and work with.

    The inclusion of a more refined metadata field would be useful, instead of just the metrics.
    """

    request: Request
    """The original request that this response corresponds to."""
    data: Any
    """The actual data returned in the response. This can be of any type, depending on the request and the ESI endpoint. Usually a json list or dict."""
    metrics: dict[str, Any] = field(default_factory=dict[str, Any])
    """Performance metrics related to the processing of the request and generation of the response. This can include things like execution time, cache hits/misses, etc."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the response data with the specified indentation."""
        root_model = ResponseDataRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> ResponseData:
        """Parse the response data from a JSON string."""
        value = ResponseDataRoot.model_validate_json(json_str).root
        return value


ResponseDataRoot = RootModel[ResponseData]


@dataclass(slots=True, kw_only=True, frozen=True)
class ResponseDataGroup:
    """Represents the data returned in a successful response to a group of ESI requests."""

    responses: dict[UUID, ResponseData] = field(
        default_factory=dict[UUID, ResponseData]
    )
    """The responses in ResponseData format."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the group response data with the specified indentation."""
        root_model = ResponseDataGroupRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> ResponseDataGroup:
        """Parse the group response data from a JSON string."""
        value = ResponseDataGroupRoot.model_validate_json(json_str).root
        return value


ResponseDataGroupRoot = RootModel[ResponseDataGroup]


@dataclass(slots=True, kw_only=True)
class ResponseDebugGroup:
    """Represents debug information included in the response to a group of ESI requests.

    Contains only the errors generated during the processing of the request group,
    and the original request group itself.
    """

    request_group: RequestGroup
    """The original request group that this response group corresponds to."""
    # These fields are determined during validation.
    invalid_requests: dict[UUID, InvalidRequest] = field(
        default_factory=dict[UUID, InvalidRequest]
    )
    """The requests that failed validation."""
    invalid_actions: list[ValidatedRequestGroupAction] = field(
        default_factory=list[ValidatedRequestGroupAction]
    )

    # These fields are determined prior to executing the requests in the group.
    metrics: RuntimeGroupMetrics = field(default_factory=RuntimeGroupMetrics)
    invalid_runtime_requests: dict[UUID, InvalidRuntimeRequest] = field(
        default_factory=dict[UUID, InvalidRuntimeRequest]
    )
    """The requests that failed the transition from Validated to Runtime."""
    # These fields are determined after the requests are executed
    failed_runtime_responses: dict[UUID, FailedRuntimeResponse] = field(
        default_factory=dict[UUID, FailedRuntimeResponse]
    )
    """The requests that failed during execution."""

    def to_string(self, indent: int) -> str:
        """Return a string representation of the ResponseDebugGroup with the specified indentation."""
        root_model = ResponseDebugGroupRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> ResponseDebugGroup:
        """Parse the ResponseDebugGroup from a JSON string."""
        value = ResponseDebugGroupRoot.model_validate_json(json_str).root
        return value


ResponseDebugGroupRoot = RootModel[ResponseDebugGroup]
