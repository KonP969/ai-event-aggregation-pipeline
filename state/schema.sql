-- Stan agenta (ST-110). Reprodukowalny z tego pliku. SQLite, jeden plik w data/.
CREATE TABLE IF NOT EXISTS events (
    id             TEXT PRIMARY KEY,          -- sha1(dedup_key)[:16]
    dedup_key      TEXT UNIQUE NOT NULL,      -- normalized(title)+date+miasto/venue
    source         TEXT NOT NULL,
    source_url     TEXT,
    category       TEXT,                      -- ai_digital | culture_family | concert
    subcategory    TEXT,
    title          TEXT NOT NULL,
    description    TEXT,
    start_datetime TEXT,                      -- ISO 8601, Europe/Warsaw
    end_datetime   TEXT,
    venue_name     TEXT,
    city           TEXT,
    address        TEXT,
    is_tricity     INTEGER,                   -- 0/1
    price_min      REAL,
    price_max      REAL,
    is_free        INTEGER,                   -- 0/1
    ticket_url     TEXT,
    artist         TEXT,
    national_scope INTEGER DEFAULT 0,         -- 0/1
    scope_reason   TEXT,
    family_suitable INTEGER,                  -- 0/1/NULL
    relevance_score REAL,
    content_hash   TEXT,                      -- do wykrycia zmian materialnych
    scraped_at     TEXT,
    delivered      INTEGER DEFAULT 0,         -- 0/1 (ST-111)
    delivered_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_delivered ON events(delivered);
CREATE INDEX IF NOT EXISTS idx_events_category  ON events(category);
