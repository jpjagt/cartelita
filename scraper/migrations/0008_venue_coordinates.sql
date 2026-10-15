-- Venue coordinates for the Today map. Filled by geocoding the venue's
-- address (cartelera.geocode, cached: only venues without coordinates are
-- looked up) or set explicitly in a venue definition. NULL = unknown; the
-- map simply leaves the venue out.
ALTER TABLE venue ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE venue ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
-- When the last geocode attempt ran (hit or miss), so misses aren't retried
-- every night.
ALTER TABLE venue ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMPTZ;
