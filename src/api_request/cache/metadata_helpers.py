"""Helpers for cache-specific response metadata handling."""

from api_request.request.models import ResponseMetadata


def merge_cached_revalidation_metadata(
    *,
    cached: ResponseMetadata,
    refreshed: ResponseMetadata,
) -> ResponseMetadata:
    """Merge a 304 revalidation response into cached response metadata.

    The returned metadata continues to describe the cached body representation,
    so it preserves the cached success status and body byte count while applying
    newer headers and timing information from the 304 revalidation response.
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
