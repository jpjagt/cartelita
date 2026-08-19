-- Instagram ingest storage layer.
--
-- 1. ig_post: one row per post ever captured, keyed by its shortcode.
--    Extraction columns (extraction/model_id/prompt_version/extracted_at)
--    stay NULL until an LLM parses it; a post is parsed at most once in
--    production (prompt_version is provenance, not a cache key — see
--    cartelera.models.IgPost).
CREATE TABLE IF NOT EXISTS ig_post (
    shortcode TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,
    handle TEXT NOT NULL,
    caption TEXT,
    posted_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    extraction JSONB,
    model_id TEXT,
    prompt_version INTEGER,
    extracted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ig_post_source_slug_idx ON ig_post (source_slug);

-- 2. ig_post_image: the raw carousel images of a post, in posted order
--    (idx). url is the CDN URL the image was downloaded from — later reused
--    as the emitted event's image_url.
CREATE TABLE IF NOT EXISTS ig_post_image (
    shortcode TEXT NOT NULL REFERENCES ig_post (shortcode) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    url TEXT NOT NULL,
    content_type TEXT NOT NULL,
    data BYTEA NOT NULL,
    PRIMARY KEY (shortcode, idx)
);

-- 3. ig_session: single-row storage of the Playwright login session
--    (storage_state), reused across captures so login only runs when it's
--    invalid.
CREATE TABLE IF NOT EXISTS ig_session (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    storage_state JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
