-- Scraper health (docs/superpowers/specs/2026-10-12-scraper-health-design.md).
--
-- 1. Event liveness: every upsert stamps last_seen_at and resets missed_runs;
--    after a HEALTHY run, a venue's upcoming events the run did not return get
--    missed_runs += 1 and are hidden (hidden_at, never deleted) at 3 misses.
--    A hidden event that reappears is un-hidden by the upsert.
ALTER TABLE event ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
ALTER TABLE event ADD COLUMN IF NOT EXISTS missed_runs INTEGER NOT NULL DEFAULT 0;
ALTER TABLE event ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ;
UPDATE event SET last_seen_at = scraped_at WHERE last_seen_at IS NULL;
CREATE INDEX IF NOT EXISTS event_venue_upcoming_visible_idx
    ON event (venue_id, start_date) WHERE hidden_at IS NULL;

-- 2. One row per source per run: verdict + metrics (source- and venue-level,
--    plus the degraded rules that fired). `acked` runs count as baseline and
--    end a bad streak (`cartelera health ack <source>`).
CREATE TABLE IF NOT EXISTS scrape_run (
    id            SERIAL PRIMARY KEY,
    source_slug   TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ,
    verdict       TEXT NOT NULL
                  CHECK (verdict IN ('healthy', 'degraded', 'broken', 'site_down')),
    error_kind    TEXT,
    error_message TEXT,
    metrics       JSONB,
    acked         BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS scrape_run_source_started_idx
    ON scrape_run (source_slug, started_at DESC);

-- 3. Per-source issue bookkeeping: the one open GitHub issue (if any) and when
--    / about what it was last commented on (comment-on-change, weekly cap).
CREATE TABLE IF NOT EXISTS source_health (
    source_slug            TEXT PRIMARY KEY,
    issue_number           INTEGER,
    issue_kind             TEXT,
    last_comment_at        TIMESTAMPTZ,
    last_signature         TEXT,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
