-- Venue-scoped verdicts for multi-venue sources (scraper-health spec,
-- revision 2026-10-13): venues degraded for VENUE_REVIEW_STREAK+ runs are
-- listed on the source's rolling venue-review issue. Comment-on-change /
-- weekly-cap bookkeeping for that section (per-venue verdicts themselves live
-- in scrape_run.metrics: "degraded_venues", "acked_venues").
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS venue_review_signature TEXT;
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS venue_review_comment_at TIMESTAMPTZ;
