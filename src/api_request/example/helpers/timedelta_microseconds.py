"""Helper functions for working with timedelta objects in microseconds."""

from datetime import timedelta


def in_microseconds(td: timedelta) -> int:
    """Convert a timedelta to microseconds."""
    return (td.days * 86400 + td.seconds) * 1_000_000 + td.microseconds


def in_nanoseconds(td: timedelta) -> int:
    """Convert a timedelta to nanoseconds."""
    return in_microseconds(td) * 1_000
