"""Tests for intermediate request model helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from pfmsoft.api_request.request.intermediate_models import RequestFromStaleCache
from pfmsoft.api_request.request.models import Request


def _request() -> Request:
    return Request(
        request_key=uuid4(),
        url="https://example.invalid/data",
        method="GET",
    )


def test_request_from_stale_cache_requires_validator() -> None:
    """Conditional header builder should require at least one validator."""
    stale = RequestFromStaleCache(
        request=_request(),
        cache_key=uuid4(),
        etag=None,
        last_modified=None,
    )

    with pytest.raises(ValueError, match="At least one of ETag or Last-Modified"):
        _ = stale.conditional_headers


def test_request_from_stale_cache_builds_headers_for_each_validator() -> None:
    """Conditional header builder should include provided validator values."""
    with_etag = RequestFromStaleCache(
        request=_request(),
        cache_key=uuid4(),
        etag='"etag-1"',
        last_modified=None,
    )
    with_last_modified = RequestFromStaleCache(
        request=_request(),
        cache_key=uuid4(),
        etag=None,
        last_modified="Mon, 06 Jul 2026 17:00:00 GMT",
    )

    assert with_etag.conditional_headers == {"If-None-Match": '"etag-1"'}
    assert with_last_modified.conditional_headers == {
        "If-Modified-Since": "Mon, 06 Jul 2026 17:00:00 GMT"
    }
