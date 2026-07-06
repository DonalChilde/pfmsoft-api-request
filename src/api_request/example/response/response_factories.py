"""Factory methods to transform responses."""

import json
from dataclasses import asdict
from typing import Any
from uuid import UUID

from esi_link.response.models import (
    ResponseData,
    ResponseDataGroup,
    ResponseDebugGroup,
    ResponseGroup,
)
from esi_link.runtime.models import RuntimeGroup


def response_group_to_response_data(
    response_group: ResponseGroup,
) -> dict[UUID, ResponseData]:
    """Convert a ResponseGroup to a dictionary of ResponseData."""
    request_group = response_group.request_group
    responses_data = {
        request_id: ResponseData(
            request=request_group.requests[request_id],
            data=json.loads(response.http_response.text),
            metrics=asdict(response.metrics),
        )
        for request_id, response in response_group.responses.items()
    }
    return responses_data


def response_group_to_response_data_group(
    response_group: ResponseGroup,
) -> ResponseDataGroup:
    """Convert a ResponseGroup to a ResponseDataGroup."""
    responses_data = response_group_to_response_data(response_group)
    return ResponseDataGroup(responses=responses_data)


def runtime_group_to_response_debug_group(
    runtime_group: RuntimeGroup,
) -> ResponseDebugGroup | None:
    """Convert a RuntimeGroup to a ResponseDebugGroup.

    Returns None if there are no errors.
    """
    if (
        runtime_group.invalid_requests
        or runtime_group.invalid_actions
        or runtime_group.invalid_runtime_requests
        or runtime_group.failed_runtime_responses
    ):
        return ResponseDebugGroup(
            request_group=runtime_group.request_group,
            invalid_requests=runtime_group.invalid_requests,
            invalid_actions=runtime_group.invalid_actions,
            invalid_runtime_requests=runtime_group.invalid_runtime_requests,
            failed_runtime_responses=runtime_group.failed_runtime_responses,
        )
    return None


def response_to_data_only(response: ResponseGroup) -> dict[str, Any]:
    """Convert a ResponseGroup to a data-only format."""
    data = {
        str(request_id): json.loads(response.http_response.text)
        for request_id, response in response.responses.items()
    }
    return data
