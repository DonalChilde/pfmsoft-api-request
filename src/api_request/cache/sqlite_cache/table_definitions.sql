-- Table definitions for the api-requester web cache SQLite database.
-- Columns that store JSON data are defined as BLOB to allow for efficient storage and retrieval.
-- timestamps are stored as nanosecond integers unless otherwise noted.


-- The WebCache table stores cached responses from web endpoints.
-- cache_key is a unique string identifier for the cached response.
-- response_text is the raw text of the response, stored as bytes for efficient retrieval
-- response_metadata_json is the metadata of the response (status code, headers, etc.) stored as JSON in a BLOB
-- etag is the ETag header value from the response, if present, stored as TEXT
-- last_modified is the Last-Modified header value from the response, if present, stored as TEXT
-- expires_at is the expiration time of the cached response, stored as a Unix timestamp in seconds, if present
CREATE TABLE IF NOT EXISTS WebCache (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    response_text BLOB NOT NULL,
    response_metadata_json BLOB NOT NULL,
    etag TEXT,
    last_modified TEXT,
    expires_at INTEGER,
    timestamped INTEGER NOT NULL
);