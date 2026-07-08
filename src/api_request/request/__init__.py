"""Request orchestration package.

This package contains:
        - Public request/response data models.
        - Internal intermediate models used by the orchestration pipeline.
        - The requester implementation and protocol contract.

Most callers should import public request types from `api_request` package
root exports (`Request`, `Response`, `ResponseMetadata`, `Source`) and use
`ApiRequester` as an async context manager.
"""
