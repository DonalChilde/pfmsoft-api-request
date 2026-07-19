"""Tests for public request/response models."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from pfmsoft.api_request.request.models import (
    FailedResponse,
    Request,
    Response,
    ResponseMetadata,
    Responses,
    Source,
)


def _build_request() -> Request:
    return Request(
        request_key=uuid4(),
        url="https://example.invalid/resource",
        method="GET",
    )


def _build_metadata(*, headers: tuple[tuple[str, str], ...]) -> ResponseMetadata:
    return ResponseMetadata(
        status_code=200,
        reason_phrase="OK",
        url="https://example.invalid/resource",
        elapsed=10,
        bytes_downloaded=2,
        headers=headers,
        received_timestamp=1_000_000,
    )


def test_response_metadata_accessors_cover_cache_and_ratelimit_fields() -> None:
    """Metadata accessors should parse common cache and rate limit headers."""
    metadata = _build_metadata(
        headers=(
            ("Date", "Mon, 06 Jul 2026 18:00:00 GMT"),
            ("Expires", "Mon, 06 Jul 2026 18:01:00 GMT"),
            ("Cache-Control", "public, max-age=60"),
            ("ETag", '"etag-1"'),
            ("Last-Modified", "Mon, 06 Jul 2026 17:00:00 GMT"),
            ("X-Pages", "3"),
            ("X-RateLimit-Group", "group-a"),
            ("X-RateLimit-Limit", "100"),
            ("X-RateLimit-Remaining", "90"),
            ("X-RateLimit-Used", "10"),
        )
    )

    assert metadata.etag == '"etag-1"'
    assert metadata.last_modified == "Mon, 06 Jul 2026 17:00:00 GMT"
    assert metadata.cache_control == "public, max-age=60"
    assert metadata.max_age == 60
    assert metadata.expires == "Mon, 06 Jul 2026 18:01:00 GMT"
    assert metadata.date_as_instant is not None
    assert metadata.expires_at is not None
    assert metadata.pages == 3
    assert metadata.ratelimit.group == "group-a"
    assert metadata.ratelimit.limit == "100"
    assert metadata.ratelimit.remaining == "90"
    assert metadata.ratelimit.used == "10"
    assert metadata.received_at.timestamp_nanos() == 1_000_000


def test_response_metadata_handles_invalid_header_values() -> None:
    """Invalid date/cache values should fail gracefully instead of raising."""
    metadata = _build_metadata(
        headers=(
            ("Date", "not-a-date"),
            ("Expires", "also-not-a-date"),
            ("Cache-Control", "max-age=abc"),
            ("X-Pages", "1"),
        )
    )

    assert metadata.date_as_instant is None
    assert metadata.max_age is None
    assert metadata.expires_at is None


def test_response_metadata_expires_at_falls_back_when_date_parse_fails() -> None:
    """Invalid Date with max-age should fall back to Expires parsing."""
    metadata = _build_metadata(
        headers=(
            ("Date", "bad-date"),
            ("Cache-Control", "max-age=60"),
            ("Expires", "Mon, 06 Jul 2026 18:01:00 GMT"),
        )
    )

    assert metadata.expires_at is not None


def test_response_metadata_date_as_instant_is_none_when_date_missing() -> None:
    """date_as_instant should return None when the Date header is absent."""
    metadata = _build_metadata(headers=(("ETag", '"etag-1"'),))

    assert metadata.date is None
    assert metadata.date_as_instant is None


def test_response_metadata_received_at_raises_when_unset() -> None:
    """received_at should raise when received_timestamp is not initialized."""
    metadata = ResponseMetadata(
        status_code=200,
        reason_phrase="OK",
        url="https://example.invalid/resource",
        elapsed=10,
        bytes_downloaded=2,
        headers=(),
        received_timestamp=-1,
    )

    with pytest.raises(ValueError, match="Received timestamp is not set"):
        _ = metadata.received_at


def test_response_metadata_duplicate_headers_log_warning(caplog) -> None:
    """Case-insensitive duplicate headers should emit a warning message."""
    caplog.set_level(logging.WARNING)

    _build_metadata(headers=(("ETag", '"one"'), ("etag", '"two"')))

    assert any("Duplicate headers found" in rec.message for rec in caplog.records)


def test_response_and_responses_serialization_roundtrip() -> None:
    """Response containers should serialize and deserialize to equivalent objects."""
    request = _build_request()
    metadata = _build_metadata(headers=(("Date", "Mon, 06 Jul 2026 18:00:00 GMT"),))

    response = Response(
        metadata=metadata,
        json={"ok": True},
        request=request,
        source=Source.NETWORK,
    )
    failed = FailedResponse(
        request=request,
        metadata=metadata,
        json={"error": "bad"},
        error_messages=["bad"],
    )
    responses = Responses(
        successful={request.request_key: response},
        failed={request.request_key: failed},
    )

    assert Response.deserialize(response.serialize(indent=2)) == response
    assert Responses.from_string(responses.to_string(indent=2)) == responses


def test_response_metadata_as_string_returns_json_payload() -> None:
    """as_string should emit a JSON payload containing status metadata."""
    metadata = _build_metadata(headers=(("Date", "Mon, 06 Jul 2026 18:00:00 GMT"),))

    metadata_json = metadata.serialize()

    assert '"status_code":200' in metadata_json
    assert '"url":"https://example.invalid/resource"' in metadata_json
