from esi_link.actions.protocols import (
    CONTEXT,
    ActionProtocol,
    GroupActionProtocol,
)
from esi_link.response.models import (
    ResponseGroup,
)
from esi_link.runtime.models import (
    FailedRuntimeResponse,
    RuntimeResponse,
)
from esi_link.validation.models import (
    ValidatedRequestAction,
    ValidatedRequestGroupAction,
)


def get_response_action_instance(action: ValidatedRequestAction) -> ActionProtocol:
    """Instance an action based on the action type and parameters in the ValidatedRequestAction."""
    # Implement the logic to retrieve the action instance from the store based on the action type
    # and parameters in the ValidatedRequestAction
    ...


def get_group_response_action_instance(
    action: ValidatedRequestGroupAction,
) -> GroupActionProtocol:
    """Instance a group action based on the action type and parameters in the ValidatedRequestGroupAction."""
    # Implement the logic to retrieve the group action instance from the store based on the action type
    # and parameters in the ValidatedRequestGroupAction
    ...


async def do_response_action(
    action: ActionProtocol,
    response: RuntimeResponse | FailedRuntimeResponse,
    context: CONTEXT,
) -> tuple[RuntimeResponse | FailedRuntimeResponse, CONTEXT]:
    """Do the response action with the given response and context.

    Return the possibly modified response and context.

    Note that actions are only performed on successful responses. To handle actions on
    failed responses, use group actions, which have access to the entire response group
    and can perform actions on failed responses as well.
    """
    response, context = action.do_action(response, context)
    return response, context


async def do_group_response_action(
    action: GroupActionProtocol, response_group: ResponseGroup, context: CONTEXT
) -> tuple[ResponseGroup, CONTEXT]:
    """Do the group response action with the given response group and context, and return the possibly modified response group and context."""
    # Implement the logic for handling the group response action here
    return response_group, context
