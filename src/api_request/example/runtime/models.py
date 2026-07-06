"""This module defines the models for representing the runtime state of ESI requests and request groups in the ESI Link system."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from esi_link.cache.models import CacheAction, CachedResponseStatus
from esi_link.execution.models import HttpResponse
from esi_link.request.models import RequestGroup
from esi_link.validation.models import (
    InvalidRequest,
    ValidatedRequest,
    ValidatedRequestAction,
    ValidatedRequestGroupAction,
)
from pydantic import RootModel
from whenever import Instant


@dataclass(slots=True, kw_only=True, frozen=True)
class RuntimeResponseAction:
    """Represents an action to be taken after receiving a response for a request."""

    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(slots=True, kw_only=True)
class PagedResponseMetrics:
    """Performance metrics for a paged response."""

    paged_requests_start: int | None = None
    paged_requests_completed: int | None = None
    additional_pages_count: int = 0


@dataclass(slots=True, kw_only=True)
class CachedResponseMetrics:
    """Performance metrics for a cached response."""

    cache_check_started: int | None = None
    cache_check_completed: int | None = None
    cache_action_started: int | None = None
    cache_action_completed: int | None = None


@dataclass(slots=True, kw_only=True)
class RuntimeRequestMetrics:
    """Performance metrics for a RuntimeRequest."""

    task_started: int | None = None
    task_completed: int | None = None
    http_request_started: int | None = None
    http_request_completed: int | None = None
    page_metrics: PagedResponseMetrics | None = None
    cache_status: CachedResponseStatus | None = None
    cache_action: CacheAction | None = None
    cache_metrics: CachedResponseMetrics | None = None

    @property
    def cache_action_duration(self) -> float:
        """Calculate the duration of adding a response to the cache."""
        if self.cache_metrics is None:
            return -1.0
        metrics = self.cache_metrics
        if (
            metrics.cache_action_started is not None
            and metrics.cache_action_completed is not None
        ):
            return (
                Instant.from_timestamp_nanos(metrics.cache_action_completed)
                - Instant.from_timestamp_nanos(metrics.cache_action_started)
            ).total("seconds")
        return -1.0

    @property
    def task_duration(self) -> float:
        """Calculate the total duration of the task."""
        if self.task_started is not None and self.task_completed is not None:
            return (
                Instant.from_timestamp_nanos(self.task_completed)
                - Instant.from_timestamp_nanos(self.task_started)
            ).total("seconds")
        return -1.0

    @property
    def primary_request_duration(self) -> float:
        """Calculate the duration of the primary request."""
        if (
            self.http_request_started is not None
            and self.http_request_completed is not None
        ):
            return (
                Instant.from_timestamp_nanos(self.http_request_completed)
                - Instant.from_timestamp_nanos(self.http_request_started)
            ).total("seconds")
        return -1.0

    @property
    def paged_requests_duration(self) -> float:
        """Calculate the total duration of the paged requests."""
        if self.page_metrics is None:
            return -1.0
        metrics = self.page_metrics
        if (
            metrics.paged_requests_start is not None
            and metrics.paged_requests_completed is not None
        ):
            return (
                Instant.from_timestamp_nanos(metrics.paged_requests_completed)
                - Instant.from_timestamp_nanos(metrics.paged_requests_start)
            ).total("seconds")
        return -1.0

    @property
    def cache_check_duration(self) -> float:
        """Calculate the duration of the cache check."""
        if self.cache_metrics is None:
            return -1.0
        metrics = self.cache_metrics
        if (
            metrics.cache_check_started is not None
            and metrics.cache_check_completed is not None
        ):
            return (
                Instant.from_timestamp_nanos(metrics.cache_check_completed)
                - Instant.from_timestamp_nanos(metrics.cache_check_started)
            ).total("seconds")
        return -1.0


@dataclass(slots=True, kw_only=True)
class RuntimeGroupMetrics:
    """Performance metrics for a RuntimeRequestGroup."""

    group_execution_started: int | None = None
    group_execution_completed: int | None = None
    request_metrics: dict[UUID, RuntimeRequestMetrics] = field(
        default_factory=dict[UUID, RuntimeRequestMetrics]
    )

    @property
    def group_execution_duration(self) -> float:
        """Calculate the total duration of the group execution."""
        if (
            self.group_execution_started is not None
            and self.group_execution_completed is not None
        ):
            return (
                Instant.from_timestamp_nanos(self.group_execution_completed)
                - Instant.from_timestamp_nanos(self.group_execution_started)
            ).total("seconds")
        return -1.0


@dataclass(slots=True, kw_only=True, frozen=True)
class RuntimeRequest:
    request_id: UUID
    """The unique identifier for the request. This is used to link the request to various objects during the request lifecycle."""

    # Other fields from the validated request as required.
    method: str = "NOT_SET"
    query_parameters: dict[str, str | int | float] = field(
        default_factory=dict[str, str | int | float]
    )
    json_body: dict[str, Any] | None = None
    is_paged: bool = False

    # These fields are determined prior to executing the request.
    resolved_path_url: str = ""
    """The resolved URL for the request, after filling in the path parameters in the URL template."""
    cache_url: str = ""
    """The URL used for caching the request, which is the resolved path url plus most query parameters. 
    This is used to generate the cache UUID for a  request. For paged requests, the 
    cache_url does not include the page query parameter, so that all pages of a paged 
    request can be identified as the same request for caching purposes."""
    additional_query_parameters: dict[str, str | int | float] = field(
        default_factory=dict[str, str | int | float]
    )
    """Additional query parameters that are not defined in the request, but are needed 
    for the request. Including things like the page number for paged requests."""
    headers: dict[str, str] = field(default_factory=dict[str, str])
    """Includes UserAgent, If-None-Match, If-Modified-Since, X-Compatibility-Date, and 
    Bearer token if required."""
    timeout: int = 10
    """The timeout for the request, in seconds."""
    cache_key: UUID | None = None
    """Cache key for the request, if applicable. This is used to identify cached responses. 
    Paged requests only have a cache key for the first page."""
    # metrics: RuntimeRequestMetrics = field(default_factory=RuntimeRequestMetrics)
    parent_id: UUID | None = None
    """The request_id of the parent request if this request is a sub-request, e.g. a paged 
    request or a retry."""
    validated_actions: list[ValidatedRequestAction] = field(
        default_factory=list[ValidatedRequestAction]
    )
    """The actions that were validated for this request. These are used to determine what actions to take after receiving the response for this request."""


@dataclass(slots=True, kw_only=True, frozen=True)
class InvalidRuntimeRequest:
    """This object is created during the creation of a RuntimeRequest from a Validated Request."""

    validated_request: ValidatedRequest
    """The original validated request."""
    failure_msg: str
    """The reason why the RuntimeRequest could not be created from the ValidatedRequest."""


@dataclass(slots=True, kw_only=True, frozen=True)
class RuntimeResponse:
    request_id: UUID
    http_response: HttpResponse
    metrics: RuntimeRequestMetrics = field(default_factory=RuntimeRequestMetrics)
    # runtime_request: RuntimeRequest


@dataclass(slots=True, kw_only=True, frozen=True)
class FailedRuntimeResponse:
    runtime_request: RuntimeRequest
    http_response: HttpResponse | None
    metrics: RuntimeRequestMetrics = field(default_factory=RuntimeRequestMetrics)
    failure_msg: str = ""


@dataclass(slots=True, kw_only=True)
class RuntimeGroup:
    """Represents the runtime state of a request group as it is being processed through the system."""

    request_group: RequestGroup
    """The original request group that this runtime group corresponds to."""
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
    runtime_responses: dict[UUID, RuntimeResponse] = field(
        default_factory=dict[UUID, RuntimeResponse]
    )
    """A mapping of request_id to RuntimeResponse for all requests in the group."""
    failed_runtime_responses: dict[UUID, FailedRuntimeResponse] = field(
        default_factory=dict[UUID, FailedRuntimeResponse]
    )
    """The requests that failed during execution."""

    @property
    def group_id(self) -> UUID:
        """The unique identifier for the request group.

        This is used to link the request group to various objects during the request group lifecycle.
        """
        return self.request_group.group_id

    def to_string(self, indent: int) -> str:
        """Convert the runtime group to a JSON string."""
        root_model = RunTimeGroupRoot(self)
        json_str = root_model.model_dump_json(indent=indent)
        return json_str

    @classmethod
    def from_string(cls, json_str: str) -> RuntimeGroup:
        """Parse the runtime group from a JSON string."""
        value = RunTimeGroupRoot.model_validate_json(json_str).root
        return value


RunTimeGroupRoot = RootModel[RuntimeGroup]
