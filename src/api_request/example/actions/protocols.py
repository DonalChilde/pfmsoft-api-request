from typing import Any, Protocol

from esi_link.response.models import ResponseGroup
from esi_link.runtime.models import FailedRuntimeResponse, RuntimeResponse

type CONTEXT = dict[str, Any]


class ActionProtocol(Protocol):
    """Protocol for actions that can be executed after receiving a response for a request."""

    def do_action(
        self,
        response: RuntimeResponse | FailedRuntimeResponse,
        context: CONTEXT,
    ) -> tuple[RuntimeResponse | FailedRuntimeResponse, CONTEXT]:
        """Execute the action with the given response."""
        ...


class GroupActionProtocol(Protocol):
    """Protocol for actions that can be executed after receiving a group of responses."""

    def do_action(
        self, response_group: ResponseGroup, context: CONTEXT
    ) -> tuple[ResponseGroup, CONTEXT]:
        """Execute the action with the given responses."""
        ...
