-- Table definitions for the Esi-Link app-data SQLite database.
-- Columns that store JSON data are defined as BLOB to allow for efficient storage and retrieval.
-- timestamps are stored as nanosecond integers unless otherwise noted.

-- The OauthMetadataCache table stores cached OAuth metadata for ESI.
-- This is designed to support a single entry.
CREATE TABLE IF NOT EXISTS OauthMetadataCache (
    ID INTEGER PRIMARY KEY CHECK (ID=0),
    timestamped INTEGER NOT NULL,
    metadata_json BLOB NOT NULL
);

-- The SchemaCache table stores cached ESI schema data.
-- This table is designed to support multiple schemas, but only one per compatibility date.
CREATE TABLE IF NOT EXISTS SchemaCache (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamped INTEGER NOT NULL,
    compatibility_date TEXT NOT NULL UNIQUE,
    schema_json BLOB NOT NULL
);

-- The CompatibilityDatesCache table stores cached compatibility dates for ESI.
-- This is designed to support a single entry.
CREATE TABLE IF NOT EXISTS CompatibilityDatesCache (
    ID INTEGER PRIMARY KEY CHECK (ID=0),
    timestamped INTEGER NOT NULL,
    compatibility_dates_json BLOB NOT NULL
);

-- The Credentials table stores the app's ESI credentials and related information.
-- At the moment, this is designed to support a single set of credentials, 
-- but multiple sets of credentials could be supported in the future.
CREATE TABLE IF NOT EXISTS Credentials (
    ID INTEGER PRIMARY KEY CHECK (ID=0),
    app_name TEXT NOT NULL,
    app_description TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    callback_url TEXT NOT NULL,
    scopes_json BLOB NOT NULL,
    timestamped INTEGER NOT NULL
);

-- The CharacterTokens table stores access and refresh tokens for ESI characters.
-- expires_at is stored as a Unix timestamp in seconds.
-- If multiple sets of credentials are supported in the future, 
--   this table may need to be updated to associate tokens with specific credentials.
CREATE TABLE IF NOT EXISTS CharacterTokens (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL UNIQUE,
    character_name TEXT NOT NULL,
    oauth_token_json BLOB NOT NULL,
    expires_at INTEGER NOT NULL,
    timestamped INTEGER NOT NULL
);

-- The WebCache table stores cached responses from ESI endpoints.
-- cache_key is a unique identifier for the cached response, a UUID
-- response_text is the raw text of the response, stored as TEXT for efficient retrieval
-- response_metadata_json is the metadata of the response (status code, headers, etc.) stored as JSON in a BLOB
-- etag is the ETag header value from the response, if present, stored as TEXT
-- expires_at is the expiration time of the cached response, stored as a Unix timestamp in seconds, if present
CREATE TABLE IF NOT EXISTS WebCache (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    response_text TEXT NOT NULL,
    response_metadata_json BLOB NOT NULL,
    etag TEXT,
    expires_at INTEGER,
    timestamped INTEGER NOT NULL
);