-- Multi-city support (Yerevan).
--
-- 1. event.language: display-only performance/source language on the price
--    convention — free text exactly as the source states it ("VOSE", "hy",
--    "non-verbal"), NULL = unknown, never parsed or inferred.
ALTER TABLE event ADD COLUMN IF NOT EXISTS language TEXT;

-- 2. venue.instagram_url: venue's Instagram profile; also the pointer for the
--    social-media ingest path.
ALTER TABLE venue ADD COLUMN IF NOT EXISTS instagram_url TEXT;

-- 3. List slugs become unique PER CITY (every city gets its own "jazz" list).
--    The original global UNIQUE constraint got the default name list_slug_key.
ALTER TABLE list DROP CONSTRAINT IF EXISTS list_slug_key;
DO $$
BEGIN
    ALTER TABLE list ADD CONSTRAINT list_city_slug_key UNIQUE (city_id, slug);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN
    NULL;  -- already applied; migrations must be idempotent
END $$;
