-- Table definitions for the api-request web cache SQLite database.
-- JSON payload columns are stored as TEXT.
-- Timestamps are stored as integers; units vary by column.


-- The WebCache table stores one row per cached response key.
-- cache_key: unique key identifying a cache entry.
-- response_text: serialized response body text.
-- response_metadata_json: JSON-encoded response metadata.
-- etag: ETag validator, if present.
-- last_modified: Last-Modified validator, if present.
-- expires_at: Unix timestamp in seconds when the entry becomes stale.
-- cache_timestamp: Unix timestamp in nanoseconds for write/update time.
CREATE TABLE IF NOT EXISTS WebCache (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    response_text TEXT NOT NULL,
    response_metadata_json TEXT NOT NULL,
    etag TEXT,
    last_modified TEXT,
    expires_at INTEGER,
    cache_timestamp INTEGER NOT NULL
);