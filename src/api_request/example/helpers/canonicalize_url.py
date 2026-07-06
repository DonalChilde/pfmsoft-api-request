"""Functions to canonicalize URLs for stable hashing."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# TODO  - Add tuple pairs as possible query parameter values, use doseq=True in urlencode,
# and update type hints accordingly, to support repeated query parameters with multiple
# values (e.g. ?foo=1&foo=2). This is necessary to correctly canonicalize URLs that use
# repeated query parameters, which are common in some APIs.
def combine_and_canonicalize_url(
    path_url: str, query_parameters: dict[str, str | int | float]
) -> str:
    """Helper function to combine a path URL with query parameters and canonicalize the result."""
    path_url = path_url.strip("/")
    query_string = "&".join(
        [f"{key}={value}" for key, value in query_parameters.items()]
    )
    combined_url = f"{path_url}?{query_string}" if query_string else path_url
    combined_url = canonicalize_url(combined_url)
    return combined_url


def canonicalize_url(url: str) -> str:
    """Return a canonical form of the URL suitable for stable hashing.

    Normalizations applied:
    - Lowercase scheme and host.
    - Sort query parameters by key (then value) and re-encode.
    - Drop URL fragment.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or ""

    # Preserve multiple values and blank values; sort by key then value
    query_pairs: list[tuple[str, str]] = parse_qsl(parts.query, keep_blank_values=True)
    query_pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(query_pairs, doseq=True)

    # Drop fragment to avoid treating anchors as separate cacheable resources
    fragment = ""

    return urlunsplit((scheme, netloc, path, query, fragment))
