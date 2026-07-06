"""ESI date helpers."""

from whenever import Instant


def latest_schema_date() -> str:
    """Get the latest possible schema date as a string in the format YYYY-MM-DD.

    EVE Esi schemas update at downtime, which is currently at 11:00 UTC. Since it is not
    possible to get a schema with a future compatibility date, we can use the previous EVE
    day as the latest possible schema date.

    # TODO verify this logic against the ESI.
    # Can try to request schema for latest_schema_date, and latest_schema_date + 1 day,
    # and see if the second request fails with a 404.

    Returns:
        Latest possible schema date as a string in the format YYYY-MM-DD.
    """
    now = Instant.now()
    previous = previous_downtime(now)
    day_before_previous = previous.subtract(hours=24)
    return day_before_previous.format("YYYY-MM-DD")


def previous_downtime(instant: Instant | None = None) -> Instant:
    """Get the previous downtime before the given instant.

    EVE Esi schemas update at downtime, which is currently at 11:00 UTC. Since it is not
    possible to get a schema with a future compatibility date, we can use the previous EVE
    day as the latest possible schema date.

    Args:
        instant: The instant to find the previous downtime for.

    Returns:
        Previous downtime as an Instant. If the instant is exactly at downtime, the previous downtime will be the same as the instant.
    """
    if instant is None:
        instant = Instant.now()
    previous_dt, _ = downtime_bracket(instant)
    return previous_dt


def next_downtime(instant: Instant | None = None) -> Instant:
    """Get the next downtime after the given instant.

    EVE Esi schemas update at downtime, which is currently at 11:00 UTC. Since it is not
    possible to get a schema with a future compatibility date, we can use the previous EVE
    day as the latest possible schema date.

    Args:
        instant: The instant to find the next downtime for. If None, the current instant will be used.

    Returns:
        Next downtime as an Instant.
    """
    if instant is None:
        instant = Instant.now()
    _, next_dt = downtime_bracket(instant)
    return next_dt


def downtime_bracket(instant: Instant) -> tuple[Instant, Instant]:
    """Get the previous and next downtime around the given instant.

    EVE downtime is currently at 11:00 UTC.

    Downtime is when the servers go offline for maintenance and updates.

    Args:
        instant: The Instant to find the downtime bracket for.

    Returns:
        A tuple containing the previous downtime and the next downtime as Instants.
            If the instant is exactly at downtime, the previous downtime will be the same as the instant,
            and the next downtime will be the next downtime after the instant.
    """
    instant_date = instant.format("YYYY-MM-DD")
    instant_date_downtime = Instant(f"{instant_date}T11:00:00Z")
    if instant < instant_date_downtime:
        previous_downtime = instant_date_downtime.subtract(hours=24)
        next_downtime = instant_date_downtime
    elif instant > instant_date_downtime:
        previous_downtime = instant_date_downtime
        next_downtime = instant_date_downtime.add(hours=24)
    else:
        previous_downtime = instant
        next_downtime = instant_date_downtime.add(hours=24)
    return previous_downtime, next_downtime
