-- Cartelera initial schema.
-- Categories of cultural events.
CREATE TABLE category (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,   -- 'film', 'jazz', 'classical', 'theater'
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE city (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,   -- 'barcelona'
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE venue (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    city_id     INTEGER NOT NULL REFERENCES city(id),
    address     TEXT,
    site_url    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A venue programs one or more categories.
CREATE TABLE venue_category (
    venue_id    INTEGER NOT NULL REFERENCES venue(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    PRIMARY KEY (venue_id, category_id)
);

CREATE TABLE event (
    id              SERIAL PRIMARY KEY,
    venue_id        INTEGER NOT NULL REFERENCES venue(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    image_url       TEXT,
    start_date      DATE NOT NULL,
    start_time      TIME,
    end_date        DATE,
    end_time        TIME,
    price           TEXT,            -- free text: 'free', 's.o.', '15€', ''
    source_url      TEXT NOT NULL,   -- deliberately NOT unique
    external_id     TEXT,            -- stable per-source id, for dedup
    recurrence_hint TEXT,            -- display-only label, e.g. 'every Tuesday'
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedup key tiers are enforced as partial unique indexes (see upsert.py for
-- which tier a given scraper uses). external_id tier:
CREATE UNIQUE INDEX event_venue_external_id_uidx
    ON event (venue_id, external_id) WHERE external_id IS NOT NULL;

CREATE INDEX event_start_date_idx ON event (start_date);
CREATE INDEX event_venue_idx ON event (venue_id);

CREATE TABLE event_category (
    event_id    INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, category_id)
);

-- Additional-language content for an event, scraped from that language's page.
-- The event's own title/description/source_url are the canonical (default)
-- fallback; a single-language venue produces zero rows here.
CREATE TABLE event_translation (
    id          SERIAL PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    lang        TEXT NOT NULL,       -- 'ca' / 'es' / 'en'
    title       TEXT NOT NULL,
    description TEXT,
    source_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, lang)
);

-- A list is an authored collection of venues with an optional per-venue
-- category whitelist.
CREATE TABLE list (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT 'cartelera',
    city_id     INTEGER NOT NULL REFERENCES city(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Membership of a venue in a list, with optional category whitelist.
-- whitelist_category_id NULL = include all of the venue's events in this list.
CREATE TABLE list_venue (
    id                    SERIAL PRIMARY KEY,
    list_id               INTEGER NOT NULL REFERENCES list(id) ON DELETE CASCADE,
    venue_id              INTEGER NOT NULL REFERENCES venue(id) ON DELETE CASCADE,
    whitelist_category_id INTEGER REFERENCES category(id) ON DELETE CASCADE
);
-- A venue may appear in a list either once with NULL whitelist (all categories)
-- or multiple times with specific whitelisted categories. Postgres PK columns
-- are implicitly NOT NULL, so uniqueness is enforced with partial unique indexes
-- rather than a composite PK that includes the nullable whitelist column.
CREATE UNIQUE INDEX list_venue_all_uidx
    ON list_venue (list_id, venue_id) WHERE whitelist_category_id IS NULL;
CREATE UNIQUE INDEX list_venue_cat_uidx
    ON list_venue (list_id, venue_id, whitelist_category_id) WHERE whitelist_category_id IS NOT NULL;

-- Migration bookkeeping.
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
