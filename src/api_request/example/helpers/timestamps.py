"""Helper functions for handling timestamps in ESI Link.

These functions are abstracted away to provide a single point of maintenance for any
changes related to how timestamps are handled in the application.
"""

from whenever import Instant


def get_current_instant() -> Instant:
    """Factory function to get current instant for default values.

    This function is used as a default_factory to avoid Pydantic issue with using a
    non-callable default for a non-serializable type.

    Returns:
        Current instant in time.
    """
    return Instant.now()


def get_current_timestamp() -> float:
    """Get the current timestamp as a float.

    This function is used to get the current timestamp in seconds since the epoch,
    which is a common format for storing and comparing timestamps.

    Returns:
        Current timestamp in seconds since the epoch.
    """
    return Instant.now().timestamp()


def get_current_timestamp_nano() -> int:
    """Get the current timestamp as an integer in nanoseconds.

    This function is used to get the current timestamp in nanoseconds since the epoch,
    which is a common format for storing and comparing timestamps in some contexts.

    Returns:
        Current timestamp in nanoseconds since the epoch.
    """
    return Instant.now().timestamp_nanos()
