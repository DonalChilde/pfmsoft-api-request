"""Helpers for cache-specific response metadata handling.

The primary helper in this module preserves cached-body semantics when a stale
entry is revalidated with a `304 Not Modified` network response.
"""

from pfmsoft.api_request.request.models import ResponseMetadata


def merge_cached_revalidation_metadata(
    *,
    cached: ResponseMetadata,
    refreshed: ResponseMetadata,
) -> ResponseMetadata:
    """Merge a 304 revalidation response into cached response metadata.

    The returned metadata continues to describe the cached body representation,
    so it preserves cached success/body fields while applying newer header and
    timing fields from the `304` revalidation response.

    Field precedence:
            - Preserved from `cached`: `status_code`, `reason_phrase`,
                `bytes_downloaded`.
            - Taken from `refreshed`: `url`, `elapsed`, `received_timestamp`.
            - Headers: merged case-insensitively where refreshed header values
                overwrite matching cached header names.

    Args:
            cached: Metadata associated with the currently stored cached body.
            refreshed: Metadata from a `304 Not Modified` revalidation response.

    Returns:
            A merged metadata value that still represents a successful cached body.
    """
    merged_headers = list(cached.headers)
    header_indexes = {
        key.lower(): index for index, (key, _) in enumerate(merged_headers)
    }
    for key, value in refreshed.headers:
        lower_key = key.lower()
        if lower_key in header_indexes:
            merged_headers[header_indexes[lower_key]] = (key, value)
            continue
        header_indexes[lower_key] = len(merged_headers)
        merged_headers.append((key, value))

    return ResponseMetadata(
        status_code=cached.status_code,
        reason_phrase=cached.reason_phrase,
        url=refreshed.url,
        elapsed=refreshed.elapsed,
        bytes_downloaded=cached.bytes_downloaded,
        headers=tuple(merged_headers),
        received_timestamp=refreshed.received_timestamp,
    )
