from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, kw_only=True, frozen=True)
class Action:
    """Represents an action to be taken after receiving a response for a request."""

    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(slots=True, kw_only=True, frozen=True)
class GroupAction:
    """Represents an action to be taken after receiving a group of responses."""

    action_type: str
    action_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
