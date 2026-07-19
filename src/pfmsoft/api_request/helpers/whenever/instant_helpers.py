"""Convenience helpers for current-time and relative-time calculations with whenever.Instant."""

from pfmsoft.api_request.helpers.whenever import Instant


def timestamp() -> int:
    """Return the current Unix timestamp in whole seconds."""
    return Instant.now().timestamp()


def timestamp_nanos() -> int:
    """Return the current Unix timestamp in nanoseconds."""
    return Instant.now().timestamp_nanos()


def from_now(timestamp: int) -> int:
    """Compute the signed number of seconds until a target Unix timestamp.

    Args:
        timestamp: Target Unix timestamp in whole seconds.

    Returns:
        Signed number of seconds between now and the target timestamp.
        Negative values indicate the target time is already in the past.
    """
    now = Instant.now().timestamp()
    return timestamp - now


def from_now_nanos(timestamp_nanos: int) -> int:
    """Compute the signed number of nanoseconds until a target Unix timestamp.

    Args:
        timestamp_nanos: Target Unix timestamp in nanoseconds.

    Returns:
        Signed number of nanoseconds between now and the target timestamp.
        Negative values indicate the target time is already in the past.
    """
    now_nanos = Instant.now().timestamp_nanos()
    return timestamp_nanos - now_nanos
