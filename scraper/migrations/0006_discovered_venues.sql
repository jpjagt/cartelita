-- Venues discovered at run time by an opt-out aggregator source (today:
-- jazzin.amsterdam). Such a source creates a venue for every name in its feed
-- that code doesn't override or deny; the column records which source created
-- it, so later runs treat it as one of that source's venues (metrics, miss
-- counting / hiding, ack). NULL = a venue defined in code (seeded).
ALTER TABLE venue ADD COLUMN IF NOT EXISTS discovered_by TEXT;
CREATE INDEX IF NOT EXISTS venue_discovered_by_idx
    ON venue (discovered_by) WHERE discovered_by IS NOT NULL;

-- The source's one rolling "new venues to review" GitHub issue.
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS review_issue_number INTEGER;
