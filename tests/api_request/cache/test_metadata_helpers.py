"""Tests for cache metadata merge helpers."""

from __future__ import annotations

from api_request.cache.metadata_helpers import merge_cached_revalidation_metadata
from api_request.request.models import ResponseMetadata


def _metadata(
    *,
    status_code: int,
    reason_phrase: str,
    headers: tuple[tuple[str, str], ...],
    bytes_downloaded: int,
    received_timestamp: int,
) -> ResponseMetadata:
    return ResponseMetadata(
        status_code=status_code,
        reason_phrase=reason_phrase,
        url="https://example.invalid/data",
        elapsed=10,
        bytes_downloaded=bytes_downloaded,
        headers=headers,
        received_timestamp=received_timestamp,
    )


def test_merge_cached_revalidation_metadata_replaces_and_appends_headers() -> None:
    """Merge should override matching headers and append newly observed headers."""
    cached = _metadata(
        status_code=200,
        reason_phrase="OK",
        headers=(("Date", "Mon, 06 Jul 2026 18:00:00 GMT"), ("ETag", '"v1"')),
        bytes_downloaded=11,
        received_timestamp=1_000,
    )
    refreshed = _metadata(
        status_code=304,
        reason_phrase="Not Modified",
        headers=(
            ("Date", "Mon, 06 Jul 2026 18:05:00 GMT"),
            ("Cache-Control", "max-age=120"),
        ),
        bytes_downloaded=0,
        received_timestamp=2_000,
    )

    merged = merge_cached_revalidation_metadata(cached=cached, refreshed=refreshed)

    assert merged.status_code == 200
    assert merged.reason_phrase == "OK"
    assert merged.bytes_downloaded == 11
    assert merged.received_timestamp == 2_000
    assert merged.headers == (
        ("Date", "Mon, 06 Jul 2026 18:05:00 GMT"),
        ("ETag", '"v1"'),
        ("Cache-Control", "max-age=120"),
    )
