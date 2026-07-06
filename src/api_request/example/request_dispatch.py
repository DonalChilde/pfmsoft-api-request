"""Function for dispatching requests."""

import asyncio
import logging
from uuid import UUID

from aiolimiter import AsyncLimiter
from httpx2 import AsyncClient, Client
from whenever import Instant

from esi_link.auth.token_store import TokenStore
from esi_link.execution.http_executor import (
    execute_http_request,
)
from esi_link.helpers.http_client import (
    config_async_http_client,
    config_http_client,
)
from esi_link.protocols.cache_manager import (
    CacheManagerProtocol,
)
from esi_link.request.models import (
    Request,
    RequestGroup,
)
from esi_link.response.models import (
    FailedResponse,
    Response,
    ResponseDebugGroup,
    ResponseGroup,
)
from esi_link.response.response_factories import runtime_group_to_response_debug_group
from esi_link.runtime.models import (
    FailedRuntimeResponse,
    RuntimeGroup,
    RuntimeRequest,
    RuntimeResponse,
)
from esi_link.runtime.runtime_request_factory import (
    generate_runtime_request_group,
)
from esi_link.schema.schema_cache import SchemaCache
from esi_link.validation.request_validation_factory import (
    validate_requests,
)

logger = logging.getLogger(__name__)

# TODO refactor web cache name.


async def dispatch_request(
    request: Request,
    schema_cache: SchemaCache,
    web_cache: CacheManagerProtocol,
    token_store: TokenStore | None = None,
    requests_per: float = 100.0,
    time_period: float = 60.0,
    session: Client | None = None,
    async_session: AsyncClient | None = None,
) -> tuple[ResponseGroup, ResponseDebugGroup | None]:
    """Dispatch a single request and return the response."""
    request_group = RequestGroup(
        group_id=request.request_id,
        created_on=request.created_on,
        description="Single request group",
        requests={request.request_id: request},
        group_actions=[],
    )
    response_group, debug_group = await dispatch_request_group(
        request_group=request_group,
        schema_cache=schema_cache,
        web_cache=web_cache,
        token_store=token_store,
        requests_per=requests_per,
        time_period=time_period,
        session=session,
        async_session=async_session,
    )

    return response_group, debug_group


async def dispatch_request_group(
    request_group: RequestGroup,
    schema_cache: SchemaCache,
    web_cache: CacheManagerProtocol,
    token_store: TokenStore | None = None,
    timeout_seconds: int = 10,
    requests_per: float = 100.0,
    time_period: float = 60.0,
    session: Client | None = None,
    async_session: AsyncClient | None = None,
) -> tuple[ResponseGroup, ResponseDebugGroup | None]:
    """Dispatch a group of requests and return a group of responses."""
    if session is None:
        session = config_http_client()
    runtime_group = RuntimeGroup(request_group=request_group)
    runtime_group.metrics.group_execution_started = Instant.now().timestamp_nanos()
    with session:
        valid_requests, invalid_requests = validate_requests(
            requests=runtime_group.request_group.requests,
            schema_cache=schema_cache,
            session=session,
            token_store=token_store,
        )
        runtime_group.valid_requests = valid_requests
        runtime_group.invalid_requests = invalid_requests
        # TODO Validate Group Actions and add to runtime group.
        valid_runtime_requests, invalid_runtime_requests = (
            generate_runtime_request_group(
                validated_requests=runtime_group.valid_requests,
                token_store=token_store,
                session=session,
                timeout_seconds=timeout_seconds,
            )
        )
        runtime_group.runtime_requests = valid_runtime_requests
        runtime_group.invalid_runtime_requests = invalid_runtime_requests
    responses, failed_responses = await _execute_runtime_requests(
        requests=runtime_group.runtime_requests,
        web_cache=web_cache,
        timeout_seconds=timeout_seconds,
        requests_per=requests_per,
        time_period=time_period,
        async_session=async_session,
    )
    runtime_group.runtime_responses = responses
    runtime_group.failed_runtime_responses = failed_responses
    runtime_group.metrics.group_execution_completed = Instant.now().timestamp_nanos()
    response_group = _to_response_group(
        runtime_group=runtime_group,
    )
    # If there are any errors, include a debug group with the details of the errors.
    debug_group = runtime_group_to_response_debug_group(runtime_group)
    if debug_group is not None:
        logger.error(
            "Errors occurred during request group processing. Debug information: \n%s",
            debug_group.to_string(indent=2),
        )
    return response_group, debug_group


async def _execute_runtime_requests(
    requests: dict[UUID, RuntimeRequest],
    web_cache: CacheManagerProtocol,
    timeout_seconds: int = 10,
    requests_per: float = 100.0,
    time_period: float = 60.0,
    async_session: AsyncClient | None = None,
) -> tuple[dict[UUID, RuntimeResponse], dict[UUID, FailedRuntimeResponse]]:

    if async_session is None:
        async_session = await config_async_http_client()
    rate_limiter = AsyncLimiter(requests_per, time_period)
    async with async_session:

        async def execute_with_actions(
            request: RuntimeRequest,
        ) -> RuntimeResponse | FailedRuntimeResponse:
            runtime_response = await execute_http_request(
                request=request,
                session=async_session,
                web_cache=web_cache,
                rate_limiter=rate_limiter,
            )
            assert runtime_response.http_response is not None, (
                "HTTP response should not be None for successful runtime responses."
            )

            # FIXME Actions need more thought.

            # context: dict[str, Any] = {}

            # for action in request.validated_actions:
            #     # NOTE action might modify the response, so we need to update the response variable with the result of the action.
            #     action_instance = get_response_action_instance(action)
            #     response, context = await do_response_action(
            #         action=action_instance, response=response, context=context
            #     )
            return runtime_response

        tasks = [execute_with_actions(request=request) for request in requests.values()]
        response_list = await asyncio.gather(*tasks)

    runtime_responses: dict[UUID, RuntimeResponse] = {}
    failed_runtime_responses: dict[UUID, FailedRuntimeResponse] = {}
    for response in response_list:
        if isinstance(response, FailedRuntimeResponse):
            failed_runtime_responses[response.runtime_request.request_id] = response
        else:
            runtime_responses[response.request_id] = response
    return runtime_responses, failed_runtime_responses


def _to_response_group(
    runtime_group: RuntimeGroup,
) -> ResponseGroup:
    """Convert a runtime response group to a response group."""
    responses = {
        request_id: Response(
            request_id=request_id,
            http_response=runtime_response.http_response,
            metrics=runtime_response.metrics,
        )
        for request_id, runtime_response in runtime_group.runtime_responses.items()
    }
    failed_responses = {
        request_id: FailedResponse(
            runtime_request=failed_runtime_response.runtime_request,
            http_response=failed_runtime_response.http_response,
            metrics=failed_runtime_response.metrics,
            failure_msg=failed_runtime_response.failure_msg,
        )
        for request_id, failed_runtime_response in runtime_group.failed_runtime_responses.items()
    }

    response_group = ResponseGroup(
        request_group=runtime_group.request_group,
        valid_requests=runtime_group.valid_requests,
        invalid_requests=runtime_group.invalid_requests,
        valid_actions=runtime_group.valid_actions,
        invalid_actions=runtime_group.invalid_actions,
        runtime_requests=runtime_group.runtime_requests,
        invalid_runtime_requests=runtime_group.invalid_runtime_requests,
        responses=responses,
        failed_responses=failed_responses,
        metrics=runtime_group.metrics,
    )
    return response_group
