# Cartelera MVP Vertical Slice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin but complete end-to-end slice of Cartelera: a Postgres schema for the domain model, one real Python scraper (Jamboree, a single-category jazz venue) that upserts events into the DB, and an Astro static site that renders the "jazz" category list as a chronological day-by-day agenda — a working, deployable site fed by real scraped data.

**Architecture:** A two-language monorepo. The Python `scraper/` package owns the Postgres schema (SQL migrations applied by a tiny runner), the SQLAlchemy data models, the per-venue scraper modules behind a uniform interface, and the orchestration runner that upserts each venue's events in a per-venue transaction (graceful degradation on failure). The Astro `web/` app reads Postgres directly at build time (server-only credentials) and statically renders category-list pages. The DB is the cross-language contract.

**Tech Stack:** Python 3.14 (managed by `uv`, `pyproject.toml`), SQLAlchemy 2.x + psycopg 3, pytest, httpx + BeautifulSoup4 for scraping; PostgreSQL 18 (local Homebrew, `:5432`); Astro 5 + TypeScript (pnpm), `postgres` (porsager) for build-time DB reads.

**Conventions:**
- Repo root: `/Users/jeroen/code/jpjagt/cartelera`. All paths below are relative to it.
- Local dev DB URL: `postgresql://localhost:5432/cartelera_dev`. Test DB URL: `postgresql://localhost:5432/cartelera_test`. Both read from env var `DATABASE_URL`.
- Run Python commands with `uv run` from the `scraper/` directory.
- Categories at launch: `film`, `jazz`, `classical`, `theater`. This slice only populates `jazz`.

---

## File Structure

**Python data plane — `scraper/`:**
- `scraper/pyproject.toml` — project + deps (uv-managed).
- `scraper/.env.example` — documents `DATABASE_URL`.
- `scraper/src/cartelera/__init__.py`
- `scraper/src/cartelera/db.py` — engine/session factory from `DATABASE_URL`.
- `scraper/src/cartelera/models.py` — SQLAlchemy models: City, Category, Venue, Event, EventTranslation, List, plus association tables.
- `scraper/src/cartelera/types.py` — `ScrapedEvent` + `ScrapedTranslation` dataclasses (the scraper output contract) and `ScrapeResult`.
- `scraper/src/cartelera/migrate.py` — applies SQL files in `scraper/migrations/` in order, tracks applied ones.
- `scraper/migrations/0001_initial.sql` — full initial schema.
- `scraper/src/cartelera/scrapers/__init__.py` — scraper registry.
- `scraper/src/cartelera/scrapers/base.py` — the uniform scraper interface (`Scraper` protocol/ABC).
- `scraper/src/cartelera/scrapers/jamboree.py` — the Jamboree scraper.
- `scraper/src/cartelera/upsert.py` — upsert one venue's `ScrapedEvent`s into the DB (the dedup-key logic).
- `scraper/src/cartelera/run.py` — orchestration runner + CLI (`run all`, `run <venue>`).
- `scraper/src/cartelera/seed.py` — seed cities, categories, venues, and the cartelera category lists.
- `scraper/tests/conftest.py` — pytest fixtures (test DB session, schema setup).
- `scraper/tests/test_migrate.py`, `test_models.py`, `test_jamboree.py`, `test_upsert.py`, `test_run.py`, `test_queries.py`
- `scraper/tests/fixtures/jamboree_agenda.html` — saved real HTML for offline scraper tests.
- `scraper/src/cartelera/queries.py` — read queries used by both Python tests and (conceptually mirrored by) the frontend: "events for a category list, chronological".

**Astro presentation plane — `web/`:**
- `web/package.json`, `web/astro.config.mjs`, `web/tsconfig.json`
- `web/.env.example` — documents server-only `DATABASE_URL`.
- `web/src/lib/db.ts` — server-only Postgres client.
- `web/src/lib/queries.ts` — `getCategoryLists()`, `getEventsForList(listSlug)`.
- `web/src/lib/types.ts` — TS types (`CategoryList`, `AgendaEvent`, `AgendaDay`).
- `web/src/lib/agenda.ts` — `groupEventsByDay(events)` pure function.
- `web/src/i18n/index.ts` — ca/es/en string dictionary + category-name + date-tag helpers.
- `web/src/pages/index.astro` — redirects bare `/` to the default locale.
- `web/src/pages/[locale]/index.astro` — per-locale homepage: links to category lists.
- `web/src/pages/[locale]/[list].astro` — per-locale category list page (uses `getStaticPaths`).
- `web/src/components/AgendaDay.astro`, `web/src/components/EventRow.astro`
- `web/tests/agenda.test.ts` — unit test for `groupEventsByDay`.
- `web/tests/i18n.test.ts` — unit test for the i18n dictionary.

**Root:**
- `README.md`, `.gitignore`

---

## Task 1: Repo scaffolding and gitignore

**Files:**
- Create: `.gitignore`, `README.md`, `scraper/pyproject.toml`, `scraper/.env.example`, `scraper/src/cartelera/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
# env
.env
# node / astro
node_modules/
web/dist/
web/.astro/
# os
.DS_Store
```

- [ ] **Step 2: Create `scraper/pyproject.toml`**

```toml
[project]
name = "cartelera"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
cartelera = "cartelera.run:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cartelera"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `scraper/.env.example`**

```bash
# Local dev database
DATABASE_URL=postgresql://localhost:5432/cartelera_dev
```

- [ ] **Step 4: Create `scraper/src/cartelera/__init__.py`** (empty file)

```python
```

- [ ] **Step 5: Create `README.md`**

```markdown
# Cartelera

A curated, navigable guide to a city's cultural life. Starts in Barcelona.

See `MANIFESTO.md` (philosophy), `docs/superpowers/specs/` (design), and
`docs/future-features.md` (deferred directions).

## Layout
- `scraper/` — Python data plane: schema, models, per-venue scrapers, orchestration.
- `web/` — Astro static site reading Postgres at build time.

## Dev setup
Requires PostgreSQL running locally, `uv`, and `pnpm`.

```bash
createdb cartelera_dev
createdb cartelera_test
cd scraper && uv sync --extra dev
cp .env.example .env
uv run cartelera migrate
uv run cartelera seed
uv run cartelera run all
cd ../web && pnpm install && cp .env.example .env && pnpm dev
```
```

- [ ] **Step 6: Verify uv resolves the project**

Run: `cd scraper && uv sync --extra dev`
Expected: a `.venv` is created and dependencies install without error.

- [ ] **Step 7: Commit**

```bash
git add .gitignore README.md scraper/pyproject.toml scraper/.env.example scraper/src/cartelera/__init__.py scraper/uv.lock
git commit -m "chore: scaffold cartelera monorepo (python scraper package)"
```

---

## Task 2: Database connection helper

**Files:**
- Create: `scraper/src/cartelera/db.py`, `scraper/tests/conftest.py`, `scraper/tests/test_db.py`

- [ ] **Step 1: Create `scraper/src/cartelera/db.py`**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # SQLAlchemy + psycopg 3 dialect
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def make_engine(url: str | None = None):
    return create_engine(url and url.replace("postgresql://", "postgresql+psycopg://", 1) or _url())


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
```

- [ ] **Step 2: Create `scraper/tests/conftest.py`**

```python
import os
import pytest
from sqlalchemy import text
from cartelera.db import make_engine, make_session_factory

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/cartelera_test")


@pytest.fixture(scope="session")
def engine():
    return make_engine(TEST_URL)


@pytest.fixture()
def session(engine):
    """A session with a clean schema applied per test."""
    from cartelera.migrate import apply_migrations
    # Drop and recreate public schema for full isolation.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    apply_migrations(engine)
    factory = make_session_factory(TEST_URL)
    s = factory()
    try:
        yield s
    finally:
        s.close()
```

- [ ] **Step 3: Write failing test `scraper/tests/test_db.py`**

```python
from sqlalchemy import text
from cartelera.db import make_engine

TEST_URL = "postgresql://localhost:5432/cartelera_test"


def test_engine_connects():
    engine = make_engine(TEST_URL)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
```

- [ ] **Step 4: Run test to verify it fails (migrate not yet present blocks conftest import path? no — this test doesn't use the session fixture)**

Run: `cd scraper && createdb cartelera_test 2>/dev/null; uv run pytest tests/test_db.py -v`
Expected: PASS (this verifies connectivity). If it errors importing `cartelera.migrate` via conftest, that's fine — conftest's session fixture is unused here; the collection of `test_db.py` only needs `cartelera.db`. If collection fails on the conftest import, proceed to Task 3 which creates `migrate.py`, then re-run.

- [ ] **Step 5: Commit**

```bash
git add scraper/src/cartelera/db.py scraper/tests/conftest.py scraper/tests/test_db.py
git commit -m "feat: add db engine/session helpers and test fixtures"
```

---

## Task 3: Initial schema migration + migration runner

**Files:**
- Create: `scraper/migrations/0001_initial.sql`, `scraper/src/cartelera/migrate.py`, `scraper/tests/test_migrate.py`

- [ ] **Step 1: Create `scraper/migrations/0001_initial.sql`**

```sql
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

-- Migration bookkeeping. IF NOT EXISTS because the migration runner's
-- _ensure_table() pre-creates this table before executing the SQL file.
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 2: Create `scraper/src/cartelera/migrate.py`**

```python
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def _ensure_table(conn):
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    ))


def applied_migrations(conn) -> set[str]:
    _ensure_table(conn)
    rows = conn.execute(text("SELECT filename FROM schema_migrations")).fetchall()
    return {r[0] for r in rows}


def apply_migrations(engine: Engine) -> list[str]:
    """Apply pending .sql files in filename order. Returns applied filenames."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    newly_applied: list[str] = []
    with engine.begin() as conn:
        done = applied_migrations(conn)
        for path in files:
            if path.name in done:
                continue
            conn.execute(text(path.read_text()))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": path.name},
            )
            newly_applied.append(path.name)
    return newly_applied
```

- [ ] **Step 3: Write failing test `scraper/tests/test_migrate.py`**

```python
from sqlalchemy import text, inspect
from cartelera.migrate import apply_migrations


def test_migrations_create_expected_tables(engine):
    apply_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "category", "city", "venue", "venue_category", "event",
        "event_category", "list", "list_venue", "schema_migrations",
    }
    assert expected.issubset(tables)


def test_migrations_are_idempotent(engine):
    apply_migrations(engine)
    second = apply_migrations(engine)
    assert second == []  # nothing new applied the second time


def test_source_url_is_not_unique(engine):
    apply_migrations(engine)
    indexes = inspect(engine).get_indexes("event")
    for idx in indexes:
        assert idx["column_names"] != ["source_url"], "source_url must not be unique"
```

Note: `test_migrate.py` uses the `engine` fixture directly (not `session`), and the `session` fixture drops/recreates schema per test, so these run against a clean DB. The first test in a fresh `cartelera_test` works because `apply_migrations` creates everything.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd scraper && uv run pytest tests/test_migrate.py -v`
Expected: 3 passed. (If `cartelera_test` doesn't exist: `createdb cartelera_test` first.)

- [ ] **Step 5: Commit**

```bash
git add scraper/migrations/0001_initial.sql scraper/src/cartelera/migrate.py scraper/tests/test_migrate.py
git commit -m "feat: add initial schema and migration runner"
```

---

## Task 4: SQLAlchemy models

**Files:**
- Create: `scraper/src/cartelera/models.py`, `scraper/tests/test_models.py`

- [ ] **Step 1: Create `scraper/src/cartelera/models.py`**

```python
from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    String, Text, Integer, Date, Time, DateTime, ForeignKey, Table, Column, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


venue_category = Table(
    "venue_category", Base.metadata,
    Column("venue_id", ForeignKey("venue.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
)

event_category = Table(
    "event_category", Base.metadata,
    Column("event_id", ForeignKey("event.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)


class City(Base):
    __tablename__ = "city"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)


class Venue(Base):
    __tablename__ = "venue"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"))
    address: Mapped[str | None] = mapped_column(Text)
    site_url: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[Category]] = relationship(secondary=venue_category)
    events: Mapped[list["Event"]] = relationship(back_populates="venue")


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[dt.date] = mapped_column(Date)
    start_time: Mapped[dt.time | None] = mapped_column(Time)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    end_time: Mapped[dt.time | None] = mapped_column(Time)
    price: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    recurrence_hint: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    venue: Mapped[Venue] = relationship(back_populates="events")
    categories: Mapped[list[Category]] = relationship(secondary=event_category)
    translations: Mapped[list["EventTranslation"]] = relationship(
        back_populates="event", cascade="all, delete-orphan")


class EventTranslation(Base):
    __tablename__ = "event_translation"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    lang: Mapped[str] = mapped_column(Text)        # 'ca' / 'es' / 'en'
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    event: Mapped[Event] = relationship(back_populates="translations")


class List(Base):
    __tablename__ = "list"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String, default="cartelera")
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"))


class ListVenue(Base):
    __tablename__ = "list_venue"
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("list.id", ondelete="CASCADE"))
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id", ondelete="CASCADE"))
    whitelist_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="CASCADE"), nullable=True
    )
```

- [ ] **Step 2: Write failing test `scraper/tests/test_models.py`**

```python
import datetime as dt
from cartelera.models import City, Category, Venue, Event


def test_can_create_venue_with_category_and_event(session):
    city = City(slug="barcelona", name="Barcelona")
    jazz = Category(slug="jazz", name="Jazz")
    session.add_all([city, jazz])
    session.flush()

    venue = Venue(slug="jamboree", name="Jamboree", city_id=city.id, categories=[jazz])
    session.add(venue)
    session.flush()

    ev = Event(
        venue_id=venue.id, title="Jam Session", start_date=dt.date(2026, 6, 1),
        start_time=dt.time(19, 0), price="€12", source_url="https://x/agenda/",
        external_id="41306", recurrence_hint="every Monday", categories=[jazz],
    )
    session.add(ev)
    session.commit()

    loaded = session.get(Event, ev.id)
    assert loaded.title == "Jam Session"
    assert loaded.venue.name == "Jamboree"
    assert [c.slug for c in loaded.categories] == ["jazz"]
    assert loaded.recurrence_hint == "every Monday"
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd scraper && uv run pytest tests/test_models.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add scraper/src/cartelera/models.py scraper/tests/test_models.py
git commit -m "feat: add SQLAlchemy domain models"
```

---

## Task 5: Scraper output contract + base interface

**Files:**
- Create: `scraper/src/cartelera/types.py`, `scraper/src/cartelera/scrapers/__init__.py`, `scraper/src/cartelera/scrapers/base.py`, `scraper/tests/test_types.py`

- [ ] **Step 1: Create `scraper/src/cartelera/types.py`**

```python
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field


@dataclass
class ScrapedTranslation:
    """Additional-language content for an event, scraped from its own page."""
    lang: str                            # 'ca' / 'es' / 'en'
    title: str
    description: str | None = None
    source_url: str | None = None


@dataclass
class ScrapedEvent:
    """The uniform output of every scraper: one fully-categorized occurrence.
    `title`/`description`/`source_url` are the canonical (default) content;
    `translations` holds any additional-language content (usually empty)."""
    title: str
    start_date: dt.date
    source_url: str
    category_slugs: list[str]            # one or more
    start_time: dt.time | None = None
    end_date: dt.date | None = None
    end_time: dt.time | None = None
    price: str | None = None
    description: str | None = None
    image_url: str | None = None
    external_id: str | None = None
    recurrence_hint: str | None = None
    translations: list[ScrapedTranslation] = field(default_factory=list)


@dataclass
class ScrapeResult:
    """Outcome of running one venue's scraper."""
    venue_slug: str
    ok: bool
    events: list[ScrapedEvent] = field(default_factory=list)
    error: str | None = None
```

- [ ] **Step 2: Create `scraper/src/cartelera/scrapers/base.py`**

```python
from __future__ import annotations
from typing import Protocol
from cartelera.types import ScrapedEvent


class Scraper(Protocol):
    """Uniform per-venue scraper interface.

    `venue_slug` ties the scraper to a seeded venue row.
    `scrape()` returns fully-categorized ScrapedEvents, or raises on failure.
    """
    venue_slug: str

    def scrape(self) -> list[ScrapedEvent]:
        ...
```

- [ ] **Step 3: Create `scraper/src/cartelera/scrapers/__init__.py`** (registry; jamboree added in Task 6)

```python
from cartelera.scrapers.base import Scraper

# Populated as scrapers are added. Maps venue_slug -> Scraper instance.
REGISTRY: dict[str, Scraper] = {}


def register(scraper: Scraper) -> None:
    REGISTRY[scraper.venue_slug] = scraper
```

- [ ] **Step 4: Write failing test `scraper/tests/test_types.py`**

```python
import datetime as dt
from cartelera.types import ScrapedEvent, ScrapeResult


def test_scraped_event_minimal_required_fields():
    ev = ScrapedEvent(
        title="X", start_date=dt.date(2026, 6, 1),
        source_url="https://x/", category_slugs=["jazz"],
    )
    assert ev.price is None
    assert ev.category_slugs == ["jazz"]


def test_scrape_result_defaults():
    r = ScrapeResult(venue_slug="jamboree", ok=True)
    assert r.events == [] and r.error is None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd scraper && uv run pytest tests/test_types.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/cartelera/types.py scraper/src/cartelera/scrapers/
git add scraper/tests/test_types.py
git commit -m "feat: add scraper output contract and base interface"
```

---

## Task 6: Jamboree scraper (offline, against saved HTML)

The scraper is tested against a saved HTML fixture so tests are deterministic and offline. A separate live smoke step (Step 7) fetches the real page once.

**Files:**
- Create: `scraper/src/cartelera/scrapers/jamboree.py`, `scraper/tests/test_jamboree.py`, `scraper/tests/fixtures/jamboree_agenda.html`

- [ ] **Step 1: Save the real agenda HTML as a fixture**

Run: `cd scraper && uv run python -c "import httpx; open('tests/fixtures/jamboree_agenda.html','w').write(httpx.get('https://jamboreejazz.com/agenda/', follow_redirects=True, timeout=30).text)"`
Expected: file `scraper/tests/fixtures/jamboree_agenda.html` exists and is non-trivial (> 5 KB). (Create the `tests/fixtures/` dir first if needed: `mkdir -p tests/fixtures`.)

- [ ] **Step 2: Inspect the fixture to find selectors**

Run: `cd scraper && uv run python -c "from bs4 import BeautifulSoup; s=BeautifulSoup(open('tests/fixtures/jamboree_agenda.html').read(),'html.parser'); print(s.prettify()[:4000])"`
Expected: HTML printed. Identify the repeating event container element and the child elements holding date, time, title, link, price. Use these to fill in the selectors in Step 3. **The selectors below are a starting structure — adjust them to match the actual fixture markup you observe.**

- [ ] **Step 3: Create `scraper/src/cartelera/scrapers/jamboree.py`**

```python
from __future__ import annotations
import datetime as dt
import re
import httpx
from bs4 import BeautifulSoup
from cartelera.types import ScrapedEvent
from cartelera.scrapers import register

AGENDA_URL = "https://jamboreejazz.com/agenda/"
VENUE_SLUG = "jamboree"

# Spanish/Catalan/English month names -> month number, to parse displayed dates.
_MONTHS = {
    "jan": 1, "ene": 1, "gen": 1, "feb": 2, "mar": 3, "apr": 4, "abr": 4, "abril": 4,
    "may": 5, "mai": 5, "maig": 5, "jun": 6, "juny": 6, "jul": 7, "juliol": 7,
    "aug": 8, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dec": 12, "des": 12, "dic": 12,
}


def _parse_date(text: str, today: dt.date) -> dt.date | None:
    """Parse a displayed date like '2 June' / '2 jun' into a date.
    Year is inferred: if the resulting date is > 6 months in the past, roll to next year."""
    m = re.search(r"(\d{1,2})\s+([A-Za-zçÇ]+)", text.strip())
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2)[:3].lower())
    if not mon:
        return None
    year = today.year
    candidate = dt.date(year, mon, day)
    if (today - candidate).days > 180:
        candidate = dt.date(year + 1, mon, day)
    return candidate


def _parse_time(text: str) -> dt.time | None:
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    return dt.time(int(m.group(1)), int(m.group(2))) if m else None


def parse_agenda(html: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []

    # ADJUST these selectors to the real fixture markup (see Step 2).
    for node in soup.select("article, .agenda-item, .event"):
        title_el = node.select_one("h2, h3, .title, a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue
        link_el = node.select_one("a[href]")
        source_url = link_el["href"] if link_el else AGENDA_URL
        if source_url.startswith("/"):
            source_url = "https://jamboreejazz.com" + source_url

        node_text = node.get_text(" ", strip=True)
        start_date = _parse_date(node_text, today)
        if not start_date:
            continue
        start_time = _parse_time(node_text)

        price_m = re.search(r"€\s?\d+", node_text)
        sold_out = "sold out" in node_text.lower() or "agotad" in node_text.lower()
        price = "s.o." if sold_out else (price_m.group(0).replace(" ", "") if price_m else None)

        # external_id: prefer a numeric ticket id in any href under the node.
        ext = None
        for a in node.select("a[href]"):
            mid = re.search(r"/events/(\d+)", a["href"])
            if mid:
                ext = mid.group(1)
                break

        hint = "every Monday" if "jam session" in title.lower() else None

        # Jamboree is single-language (es); canonical content only, no translations.
        events.append(ScrapedEvent(
            title=title, start_date=start_date, start_time=start_time,
            source_url=source_url, category_slugs=["jazz"], price=price,
            external_id=ext, recurrence_hint=hint,
        ))
    return events


class JamboreeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        return parse_agenda(html)


register(JamboreeScraper())
```

- [ ] **Step 4: Write test `scraper/tests/test_jamboree.py`**

```python
import datetime as dt
from pathlib import Path
from cartelera.scrapers.jamboree import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "jamboree_agenda.html"


def test_parses_at_least_one_event():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    assert len(events) >= 1


def test_events_are_jazz_categorized_with_dates():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    for ev in events:
        assert ev.category_slugs == ["jazz"]
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("http")
```

- [ ] **Step 5: Run tests; iterate on selectors until they pass**

Run: `cd scraper && uv run pytest tests/test_jamboree.py -v`
Expected: 2 passed. If 0 events parse, return to Step 2, inspect the actual markup, and adjust the `select(...)` calls and field extraction in `parse_agenda` until real events are extracted. This selector-tuning loop is expected and is the core work of this task.

- [ ] **Step 6: Add a recurrence-hint assertion once you confirm a jam session exists in the fixture**

If the fixture contains a "Jam Session" event, add to `test_jamboree.py`:

```python
def test_jam_session_has_recurrence_hint():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    jams = [e for e in events if "jam" in e.title.lower()]
    if jams:  # only assert if the saved fixture happens to include one
        assert jams[0].recurrence_hint == "every Monday"
```

Run: `cd scraper && uv run pytest tests/test_jamboree.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add scraper/src/cartelera/scrapers/jamboree.py scraper/tests/test_jamboree.py scraper/tests/fixtures/jamboree_agenda.html
git commit -m "feat: add Jamboree jazz scraper (offline-tested against fixture)"
```

---

## Task 7: Seed data (city, categories, venue, cartelera jazz list)

**Files:**
- Create: `scraper/src/cartelera/seed.py`, `scraper/tests/test_seed.py`

- [ ] **Step 1: Create `scraper/src/cartelera/seed.py`**

```python
from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue

CATEGORIES = [("film", "Film"), ("jazz", "Jazz"), ("classical", "Classical"), ("theater", "Theater")]


def seed(session: Session) -> None:
    """Idempotent seed of launch reference data for Barcelona."""
    bcn = session.query(City).filter_by(slug="barcelona").one_or_none()
    if not bcn:
        bcn = City(slug="barcelona", name="Barcelona")
        session.add(bcn)
        session.flush()

    cats: dict[str, Category] = {}
    for slug, name in CATEGORIES:
        c = session.query(Category).filter_by(slug=slug).one_or_none()
        if not c:
            c = Category(slug=slug, name=name)
            session.add(c)
            session.flush()
        cats[slug] = c

    jamboree = session.query(Venue).filter_by(slug="jamboree").one_or_none()
    if not jamboree:
        jamboree = Venue(
            slug="jamboree", name="Jamboree", city_id=bcn.id,
            address="Plaça Reial, 17, 08002 Barcelona",
            site_url="https://jamboreejazz.com",
            categories=[cats["jazz"]],
        )
        session.add(jamboree)
        session.flush()

    # cartelera-authored jazz list: jazz venues, no whitelist needed (single-cat).
    jazz_list = session.query(List).filter_by(slug="jazz").one_or_none()
    if not jazz_list:
        jazz_list = List(slug="jazz", name="Jazz", author="cartelera", city_id=bcn.id)
        session.add(jazz_list)
        session.flush()
    membership = session.query(ListVenue).filter_by(
        list_id=jazz_list.id, venue_id=jamboree.id, whitelist_category_id=None
    ).one_or_none()
    if not membership:
        session.add(ListVenue(list_id=jazz_list.id, venue_id=jamboree.id, whitelist_category_id=None))
    session.commit()
```

- [ ] **Step 2: Write test `scraper/tests/test_seed.py`**

```python
from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)  # second run must not duplicate
    assert session.query(Category).count() == 4
    assert session.query(Venue).filter_by(slug="jamboree").count() == 1
    assert session.query(List).filter_by(slug="jazz").count() == 1
    assert session.query(ListVenue).count() == 1


def test_jamboree_is_jazz(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="jamboree").one()
    assert [c.slug for c in v.categories] == ["jazz"]
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd scraper && uv run pytest tests/test_seed.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add scraper/src/cartelera/seed.py scraper/tests/test_seed.py
git commit -m "feat: add idempotent seed (barcelona, categories, jamboree, jazz list)"
```

---

## Task 8: Upsert one venue's events (dedup-key logic + category auto-tagging)

**Files:**
- Create: `scraper/src/cartelera/upsert.py`, `scraper/tests/test_upsert.py`

- [ ] **Step 1: Create `scraper/src/cartelera/upsert.py`**

```python
from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from cartelera.models import Venue, Event, Category, EventTranslation
from cartelera.types import ScrapedEvent


def _find_existing(session: Session, venue_id: int, se: ScrapedEvent) -> Event | None:
    """Apply the dedup-key tiers in priority order."""
    if se.external_id is not None:
        e = session.scalars(select(Event).where(
            Event.venue_id == venue_id, Event.external_id == se.external_id)).first()
        if e:
            return e
        return None  # external_id tier is authoritative when present
    # tier 2: (venue_id, source_url)
    e = session.scalars(select(Event).where(
        Event.venue_id == venue_id, Event.source_url == se.source_url)).first()
    if e:
        return e
    # tier 3: (venue_id, title, start_date)
    return session.scalars(select(Event).where(
        Event.venue_id == venue_id, Event.title == se.title,
        Event.start_date == se.start_date)).first()


def upsert_venue_events(session: Session, venue_slug: str, scraped: list[ScrapedEvent]) -> int:
    """Upsert all scraped events for one venue. Returns number of rows written.
    Runs in the caller's transaction; caller commits/rolls back."""
    venue = session.scalars(select(Venue).where(Venue.slug == venue_slug)).one()
    cat_by_slug = {c.slug: c for c in session.scalars(select(Category)).all()}
    written = 0
    for se in scraped:
        cats = [cat_by_slug[s] for s in se.category_slugs]
        existing = _find_existing(session, venue.id, se)
        if existing:
            ev = existing
        else:
            ev = Event(venue_id=venue.id, title=se.title,
                       start_date=se.start_date, source_url=se.source_url)
            session.add(ev)
        ev.title = se.title
        ev.start_date = se.start_date
        ev.start_time = se.start_time
        ev.end_date = se.end_date
        ev.end_time = se.end_time
        ev.price = se.price
        ev.description = se.description
        ev.image_url = se.image_url
        ev.source_url = se.source_url
        ev.external_id = se.external_id
        ev.recurrence_hint = se.recurrence_hint
        ev.scraped_at = dt.datetime.now(dt.timezone.utc)
        ev.categories = cats
        # Replace translations wholesale (canonical content lives on the event).
        ev.translations = [
            EventTranslation(lang=t.lang, title=t.title,
                             description=t.description, source_url=t.source_url)
            for t in se.translations
        ]
        written += 1
    session.flush()
    return written
```

- [ ] **Step 2: Write test `scraper/tests/test_upsert.py`**

```python
import datetime as dt
from cartelera.seed import seed
from cartelera.upsert import upsert_venue_events
from cartelera.models import Event
from cartelera.types import ScrapedEvent


def _ev(**kw):
    base = dict(title="Show", start_date=dt.date(2026, 6, 2),
                source_url="https://jamboreejazz.com/agenda/", category_slugs=["jazz"])
    base.update(kw)
    return ScrapedEvent(**base)


def test_insert_then_update_by_external_id_no_duplicate(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="41306", title="Jam")])
    session.commit()
    upsert_venue_events(session, "jamboree", [_ev(external_id="41306", title="Jam Renamed")])
    session.commit()
    rows = session.query(Event).all()
    assert len(rows) == 1
    assert rows[0].title == "Jam Renamed"


def test_reschedule_updates_date_in_place(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="9", start_date=dt.date(2026, 6, 2))])
    session.commit()
    upsert_venue_events(session, "jamboree", [_ev(external_id="9", start_date=dt.date(2026, 6, 9))])
    session.commit()
    rows = session.query(Event).all()
    assert len(rows) == 1
    assert rows[0].start_date == dt.date(2026, 6, 9)


def test_events_get_jazz_category(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="1")])
    session.commit()
    ev = session.query(Event).one()
    assert [c.slug for c in ev.categories] == ["jazz"]


def test_distinct_external_ids_create_distinct_rows(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(external_id="1"), _ev(external_id="2")])
    session.commit()
    assert session.query(Event).count() == 2


def test_translations_are_written_and_replaced(session):
    from cartelera.types import ScrapedTranslation
    from cartelera.models import EventTranslation
    seed(session)
    upsert_venue_events(session, "jamboree", [_ev(
        external_id="t", translations=[ScrapedTranslation(lang="en", title="EN title")])])
    session.commit()
    assert session.query(EventTranslation).count() == 1
    # re-scrape with a different set replaces wholesale
    upsert_venue_events(session, "jamboree", [_ev(
        external_id="t", translations=[ScrapedTranslation(lang="ca", title="CA title")])])
    session.commit()
    rows = session.query(EventTranslation).all()
    assert len(rows) == 1 and rows[0].lang == "ca"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd scraper && uv run pytest tests/test_upsert.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add scraper/src/cartelera/upsert.py scraper/tests/test_upsert.py
git commit -m "feat: add per-venue event upsert with tiered dedup key"
```

---

## Task 9: Orchestration runner + CLI (migrate / seed / run, graceful degradation)

**Files:**
- Create: `scraper/src/cartelera/run.py`, `scraper/tests/test_run.py`

- [ ] **Step 1: Create `scraper/src/cartelera/run.py`**

```python
from __future__ import annotations
import sys
from sqlalchemy.orm import Session
from cartelera.db import make_engine, make_session_factory
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db
from cartelera.upsert import upsert_venue_events
from cartelera.types import ScrapeResult
from cartelera.scrapers import REGISTRY
import cartelera.scrapers.jamboree  # noqa: F401  (registers the scraper)


def run_one(session: Session, venue_slug: str) -> ScrapeResult:
    """Scrape + upsert a single venue in its own transaction.
    On any failure, roll back so the venue's existing rows are left untouched."""
    scraper = REGISTRY[venue_slug]
    try:
        events = scraper.scrape()
        upsert_venue_events(session, venue_slug, events)
        session.commit()
        return ScrapeResult(venue_slug=venue_slug, ok=True, events=events)
    except Exception as exc:  # noqa: BLE001 - we want all failures isolated per venue
        session.rollback()
        return ScrapeResult(venue_slug=venue_slug, ok=False, error=f"{type(exc).__name__}: {exc}")


def run_all(session: Session) -> list[ScrapeResult]:
    return [run_one(session, slug) for slug in REGISTRY]


def _report(results: list[ScrapeResult]) -> None:
    for r in results:
        if r.ok:
            print(f"[ok]   {r.venue_slug}: {len(r.events)} events")
        else:
            print(f"[FAIL] {r.venue_slug}: {r.error}", file=sys.stderr)


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    engine = make_engine()
    if cmd == "migrate":
        applied = apply_migrations(engine)
        print(f"applied: {applied or 'none (up to date)'}")
        return 0
    session = make_session_factory()()
    try:
        if cmd == "seed":
            seed_db(session)
            print("seeded")
            return 0
        if cmd == "run":
            target = args[1] if len(args) > 1 else "all"
            results = run_all(session) if target == "all" else [run_one(session, target)]
            _report(results)
            return 0 if all(r.ok for r in results) else 1
    finally:
        session.close()
    print("usage: cartelera [migrate|seed|run [all|<venue_slug>]]")
    return 0
```

- [ ] **Step 2: Write test `scraper/tests/test_run.py`**

```python
import datetime as dt
from cartelera.seed import seed
from cartelera.models import Event
from cartelera.types import ScrapedEvent
from cartelera.scrapers import REGISTRY
from cartelera.run import run_one


class _FakeScraper:
    venue_slug = "jamboree"

    def __init__(self, events=None, boom=False):
        self._events = events or []
        self._boom = boom

    def scrape(self):
        if self._boom:
            raise RuntimeError("site changed")
        return self._events


def test_successful_run_writes_events(session, monkeypatch):
    seed(session)
    ev = ScrapedEvent(title="X", start_date=dt.date(2026, 6, 2),
                      source_url="https://x/", category_slugs=["jazz"], external_id="1")
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(events=[ev]))
    result = run_one(session, "jamboree")
    assert result.ok and len(result.events) == 1
    assert session.query(Event).count() == 1


def test_failing_scraper_is_isolated_and_keeps_existing_data(session, monkeypatch):
    seed(session)
    good = ScrapedEvent(title="Old", start_date=dt.date(2026, 6, 2),
                        source_url="https://x/", category_slugs=["jazz"], external_id="1")
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(events=[good]))
    run_one(session, "jamboree")
    # now the venue's scraper breaks
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(boom=True))
    result = run_one(session, "jamboree")
    assert not result.ok
    assert "site changed" in result.error
    # existing data untouched
    assert session.query(Event).count() == 1
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd scraper && uv run pytest tests/test_run.py -v`
Expected: 2 passed.

- [ ] **Step 4: Run the full Python suite**

Run: `cd scraper && uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 5: End-to-end smoke against the dev DB (real scrape)**

Run:
```bash
cd scraper
createdb cartelera_dev 2>/dev/null
export DATABASE_URL=postgresql://localhost:5432/cartelera_dev
uv run cartelera migrate
uv run cartelera seed
uv run cartelera run jamboree
```
Expected: `[ok] jamboree: N events` with N >= 1. Verify rows: `psql cartelera_dev -c "SELECT count(*) FROM event;"` → N.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/cartelera/run.py scraper/tests/test_run.py
git commit -m "feat: add orchestration runner + CLI with per-venue failure isolation"
```

---

## Task 10: Read queries (events for a category list, chronological)

**Files:**
- Create: `scraper/src/cartelera/queries.py`, `scraper/tests/test_queries.py`

This Python query mirrors the logic the frontend will run in SQL (Task 12). Implementing and testing it here validates the list/whitelist semantics against the data model before the frontend depends on them.

- [ ] **Step 1: Create `scraper/src/cartelera/queries.py`**

```python
from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from cartelera.models import List, ListVenue, Event, event_category


def events_for_list(session: Session, list_slug: str, on_or_after: dt.date) -> list[Event]:
    """Events from a list's venues, applying each venue's optional category
    whitelist, from `on_or_after` onward, chronological."""
    lst = session.scalars(select(List).where(List.slug == list_slug)).one()
    memberships = session.scalars(select(ListVenue).where(ListVenue.list_id == lst.id)).all()

    results: dict[int, Event] = {}
    for m in memberships:
        q = select(Event).where(Event.venue_id == m.venue_id, Event.start_date >= on_or_after)
        if m.whitelist_category_id is not None:
            q = q.join(event_category, event_category.c.event_id == Event.id).where(
                event_category.c.category_id == m.whitelist_category_id)
        for ev in session.scalars(q).all():
            results[ev.id] = ev  # dedupe across overlapping memberships

    return sorted(results.values(), key=lambda e: (e.start_date, e.start_time or dt.time.min))
```

- [ ] **Step 2: Write test `scraper/tests/test_queries.py`**

```python
import datetime as dt
from cartelera.seed import seed
from cartelera.upsert import upsert_venue_events
from cartelera.queries import events_for_list
from cartelera.types import ScrapedEvent


def _se(eid, d, t=None):
    return ScrapedEvent(title=f"E{eid}", start_date=d, start_time=t,
                        source_url=f"https://x/{eid}", category_slugs=["jazz"], external_id=eid)


def test_list_returns_chronological_future_events(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [
        _se("a", dt.date(2026, 6, 9), dt.time(21, 0)),
        _se("b", dt.date(2026, 6, 2), dt.time(19, 0)),
        _se("c", dt.date(2026, 6, 2), dt.time(22, 0)),
        _se("past", dt.date(2026, 5, 1)),
    ])
    session.commit()
    evs = events_for_list(session, "jazz", on_or_after=dt.date(2026, 6, 1))
    assert [e.title for e in evs] == ["E b", "E c", "E a"] or \
           [e.title for e in evs] == ["Eb", "Ec", "Ea"]
    # past event excluded
    assert all(e.start_date >= dt.date(2026, 6, 1) for e in evs)
```

Note: `f"E{eid}"` with `eid="b"` yields `"Eb"` (no space) — the assertion's first branch is defensive; the real expected order is `Eb, Ec, Ea` (date then time).

- [ ] **Step 3: Fix the test's expected values to the exact titles, run to verify**

Adjust the assertion to the single correct form (`["Eb", "Ec", "Ea"]`) and remove the defensive `or`.

Run: `cd scraper && uv run pytest tests/test_queries.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add scraper/src/cartelera/queries.py scraper/tests/test_queries.py
git commit -m "feat: add list-events read query with per-venue category whitelist"
```

---

## Task 11: Astro project scaffold

**Files:**
- Create: `web/package.json`, `web/astro.config.mjs`, `web/tsconfig.json`, `web/.env.example`, `web/src/lib/types.ts`

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "cartelera-web",
  "type": "module",
  "version": "0.1.0",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "test": "vitest run"
  },
  "dependencies": {
    "astro": "^5.0.0",
    "postgres": "^3.4.0"
  },
  "devDependencies": {
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create `web/astro.config.mjs`**

```js
import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
});
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  }
}
```

- [ ] **Step 4: Create `web/.env.example`**

```bash
# Server-only. Never prefix with PUBLIC_.
DATABASE_URL=postgresql://localhost:5432/cartelera_dev
```

- [ ] **Step 5: Create `web/src/lib/types.ts`**

```typescript
export type Locale = "ca" | "es" | "en";
export const LOCALES: Locale[] = ["ca", "es", "en"];
export const DEFAULT_LOCALE: Locale = "es";

export interface CategoryList {
  slug: string;        // also the category slug, used for name translation
}

export interface AgendaEvent {
  id: number;
  title: string;       // resolved for the active locale (translation ?? canonical)
  startDate: string;   // ISO yyyy-mm-dd
  startTime: string | null; // 'HH:MM' or null
  venueName: string;
  price: string | null;
  sourceUrl: string;   // resolved for the active locale
  recurrenceHint: string | null;
}

export interface AgendaDay {
  date: string;        // ISO yyyy-mm-dd
  events: AgendaEvent[];
}
```

- [ ] **Step 6: Install and verify Astro builds the empty project**

Run: `cd web && pnpm install && pnpm build`
Expected: install succeeds; build runs (it may warn "no pages" — acceptable at this step).

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/astro.config.mjs web/tsconfig.json web/.env.example web/src/lib/types.ts web/pnpm-lock.yaml
git commit -m "chore: scaffold astro web app"
```

---

## Task 11b: i18n dictionary (UI chrome + category names)

**Files:**
- Create: `web/src/i18n/index.ts`, `web/tests/i18n.test.ts`

- [ ] **Step 1: Create `web/src/i18n/index.ts`**

```typescript
import type { Locale } from "@/lib/types";

interface Strings {
  siteTitle: string;
  noEvents: string;
  back: string;
  // category names keyed by category slug
  categories: Record<string, string>;
}

const DICT: Record<Locale, Strings> = {
  ca: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No hi ha esdeveniments propers.",
    back: "Inici",
    categories: { film: "Cinema", jazz: "Jazz", classical: "Clàssica", theater: "Teatre" },
  },
  es: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No hay eventos próximos.",
    back: "Inicio",
    categories: { film: "Cine", jazz: "Jazz", classical: "Clásica", theater: "Teatro" },
  },
  en: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No upcoming events.",
    back: "Home",
    categories: { film: "Film", jazz: "Jazz", classical: "Classical", theater: "Theater" },
  },
};

export function t(locale: Locale): Strings {
  return DICT[locale];
}

export function categoryName(locale: Locale, slug: string): string {
  return DICT[locale].categories[slug] ?? slug;
}

/** BCP-47 tag for Intl/date formatting. */
export function localeTag(locale: Locale): string {
  return { ca: "ca-ES", es: "es-ES", en: "en-GB" }[locale];
}
```

- [ ] **Step 2: Write failing test `web/tests/i18n.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { t, categoryName, localeTag } from "@/i18n";

describe("i18n", () => {
  it("translates category names per locale", () => {
    expect(categoryName("es", "film")).toBe("Cine");
    expect(categoryName("ca", "film")).toBe("Cinema");
    expect(categoryName("en", "film")).toBe("Film");
  });

  it("falls back to slug for unknown category", () => {
    expect(categoryName("en", "opera")).toBe("opera");
  });

  it("provides locale-specific chrome and date tags", () => {
    expect(t("es").noEvents).toContain("eventos");
    expect(localeTag("ca")).toBe("ca-ES");
  });
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd web && pnpm test i18n`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/i18n/index.ts web/tests/i18n.test.ts
git commit -m "feat: add ca/es/en i18n dictionary for UI chrome and category names"
```

---

## Task 12: Frontend DB client + queries

**Files:**
- Create: `web/src/lib/db.ts`, `web/src/lib/queries.ts`

- [ ] **Step 1: Create `web/src/lib/db.ts`**

```typescript
import postgres from "postgres";

const url = import.meta.env.DATABASE_URL ?? import.meta.env.DATABASE_URL;
if (!url) throw new Error("DATABASE_URL is not set (server-only)");

// One connection for the build process; SSL required in production.
export const sql = postgres(url, {
  ssl: url.includes("localhost") ? false : "require",
});
```

- [ ] **Step 2: Create `web/src/lib/queries.ts`**

```typescript
import { sql } from "@/lib/db";
import type { CategoryList, AgendaEvent, Locale } from "@/lib/types";

export async function getCategoryLists(): Promise<CategoryList[]> {
  const rows = await sql<{ slug: string }[]>`
    SELECT slug FROM list WHERE author = 'cartelera' ORDER BY slug`;
  return rows.map((r) => ({ slug: r.slug }));
}

export async function getEventsForList(listSlug: string, locale: Locale): Promise<AgendaEvent[]> {
  // Events from the list's venues, applying each membership's optional category
  // whitelist, from today onward, chronological. Content is resolved per locale:
  // the matching event_translation if present, else the canonical event fields.
  const rows = await sql<any[]>`
    SELECT DISTINCT e.id, e.start_date, e.start_time, e.recurrence_hint,
                    v.name AS venue_name, e.price,
                    COALESCE(t.title, e.title)            AS title,
                    COALESCE(t.source_url, e.source_url)  AS source_url
    FROM list l
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE
    LEFT JOIN event_translation t ON t.event_id = e.id AND t.lang = ${locale}
    WHERE l.slug = ${listSlug}
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    ORDER BY e.start_date, e.start_time NULLS FIRST`;

  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    startDate: r.start_date instanceof Date ? r.start_date.toISOString().slice(0, 10) : String(r.start_date).slice(0, 10),
    startTime: r.start_time ? String(r.start_time).slice(0, 5) : null,
    venueName: r.venue_name,
    price: r.price,
    sourceUrl: r.source_url,
    recurrenceHint: r.recurrence_hint,
  }));
}
```

Note: `COALESCE(t.title, e.title)` is the fallback — when no `event_translation`
row exists for `locale`, the canonical event title/source_url are used. With the
MVP's single-language Jamboree (zero translations), every locale resolves to
canonical, which is exactly the intended behavior.

- [ ] **Step 3: Manually verify the query against the seeded dev DB**

Run: `cd web && DATABASE_URL=postgresql://localhost:5432/cartelera_dev pnpm exec vite-node -e "import {getEventsForList,getCategoryLists} from './src/lib/queries.ts'; console.log(await getCategoryLists()); const e = await getEventsForList('jazz','es'); console.log(e.length, e[0]); process.exit(0)"`
Expected: prints the category lists (including `{slug:'jazz'}`) and the first jazz event resolved for `es`. (Requires Task 9 Step 5 to have populated the dev DB. If `vite-node` isn't available, verify through the page build in Task 14 instead.)

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/db.ts web/src/lib/queries.ts
git commit -m "feat: add server-only postgres client and list queries for the frontend"
```

---

## Task 13: Day-grouping pure function (unit tested)

**Files:**
- Create: `web/src/lib/agenda.ts`, `web/tests/agenda.test.ts`

- [ ] **Step 1: Create `web/src/lib/agenda.ts`**

```typescript
import type { AgendaEvent, AgendaDay } from "@/lib/types";

/** Group a chronologically-sorted event list into per-day buckets, preserving order. */
export function groupEventsByDay(events: AgendaEvent[]): AgendaDay[] {
  const days: AgendaDay[] = [];
  for (const ev of events) {
    let day = days[days.length - 1];
    if (!day || day.date !== ev.startDate) {
      day = { date: ev.startDate, events: [] };
      days.push(day);
    }
    day.events.push(ev);
  }
  return days;
}
```

- [ ] **Step 2: Write failing test `web/tests/agenda.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { groupEventsByDay } from "@/lib/agenda";
import type { AgendaEvent } from "@/lib/types";

const ev = (id: number, date: string): AgendaEvent => ({
  id, title: `E${id}`, startDate: date, startTime: null,
  venueName: "Jamboree", price: null, sourceUrl: "https://x", recurrenceHint: null,
});

describe("groupEventsByDay", () => {
  it("buckets events by date, preserving order", () => {
    const days = groupEventsByDay([ev(1, "2026-06-02"), ev(2, "2026-06-02"), ev(3, "2026-06-09")]);
    expect(days.map((d) => d.date)).toEqual(["2026-06-02", "2026-06-09"]);
    expect(days[0].events.map((e) => e.id)).toEqual([1, 2]);
    expect(days[1].events.map((e) => e.id)).toEqual([3]);
  });

  it("returns empty array for no events", () => {
    expect(groupEventsByDay([])).toEqual([]);
  });
});
```

- [ ] **Step 3: Add a minimal `web/vitest.config.ts` so `@/` resolves**

```typescript
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && pnpm test`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/agenda.ts web/tests/agenda.test.ts web/vitest.config.ts
git commit -m "feat: add day-grouping helper for the agenda view"
```

---

## Task 14: Pages and components (locale-prefixed homepage + category list agenda)

Routing is **locale-prefixed**: `/ca`, `/es`, `/en` (homepage per locale) and
`/ca/jazz`, `/es/jazz`, `/en/jazz` (category list per locale). The bare `/`
redirects to the default locale. Each locale is statically pre-built.

**Files:**
- Create: `web/src/components/EventRow.astro`, `web/src/components/AgendaDay.astro`, `web/src/pages/index.astro`, `web/src/pages/[locale]/index.astro`, `web/src/pages/[locale]/[list].astro`

- [ ] **Step 1: Create `web/src/components/EventRow.astro`**

```astro
---
import type { AgendaEvent } from "@/lib/types";
interface Props { event: AgendaEvent }
const { event } = Astro.props;
---
<tr>
  <td class="time">{event.startTime ?? ""}</td>
  <td class="title">
    <a href={event.sourceUrl} target="_blank" rel="noopener">{event.title}</a>
    {event.recurrenceHint && <span class="recurs" title={event.recurrenceHint}>↻</span>}
  </td>
  <td class="venue">{event.venueName}</td>
  <td class="price">{event.price ?? ""}</td>
</tr>
<style>
  td { padding: 0.4rem 0.75rem; border-bottom: 1px solid #eee; vertical-align: top; }
  .time { white-space: nowrap; color: #444; }
  .recurs { color: #888; margin-left: 0.3rem; cursor: help; }
  .price { white-space: nowrap; color: #444; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: Create `web/src/components/AgendaDay.astro`** (date header formatted per locale)

```astro
---
import type { AgendaDay, Locale } from "@/lib/types";
import { localeTag } from "@/i18n";
import EventRow from "@/components/EventRow.astro";
interface Props { day: AgendaDay; locale: Locale }
const { day, locale } = Astro.props;
const heading = new Date(day.date + "T00:00:00").toLocaleDateString(localeTag(locale), {
  weekday: "long", day: "numeric", month: "long",
});
---
<section>
  <h2>{heading}</h2>
  <table><tbody>{day.events.map((e) => <EventRow event={e} />)}</tbody></table>
</section>
<style>
  h2 { background: #e8e8e8; padding: 0.4rem 0.75rem; font-size: 1rem; margin: 1.5rem 0 0; }
  table { width: 100%; border-collapse: collapse; }
</style>
```

- [ ] **Step 3: Create `web/src/pages/index.astro`** (redirect bare `/` to default locale)

```astro
---
import { DEFAULT_LOCALE } from "@/lib/types";
return Astro.redirect(`/${DEFAULT_LOCALE}`);
---
```

- [ ] **Step 4: Create `web/src/pages/[locale]/index.astro`**

```astro
---
import { getCategoryLists } from "@/lib/queries";
import { LOCALES, type Locale } from "@/lib/types";
import { t, categoryName } from "@/i18n";

export async function getStaticPaths() {
  return LOCALES.map((locale) => ({ params: { locale } }));
}

const locale = Astro.params.locale as Locale;
const strings = t(locale);
const lists = await getCategoryLists();
---
<html lang={locale}>
  <head><meta charset="utf-8" /><title>{strings.siteTitle}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <header><h1>{strings.siteTitle}</h1></header>
    <nav>{lists.map((l) => <a href={`/${locale}/${l.slug}`}>{categoryName(locale, l.slug)}</a>)}</nav>
    <p class="langs">{LOCALES.map((lc) => <a href={`/${lc}`}>{lc.toUpperCase()}</a>)}</p>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }
      nav a { margin-right: 1rem; font-size: 1.1rem; }
      .langs a { margin-right: 0.5rem; color: #888; font-size: 0.85rem; }
    </style>
  </body>
</html>
```

- [ ] **Step 5: Create `web/src/pages/[locale]/[list].astro`**

```astro
---
import { getCategoryLists, getEventsForList } from "@/lib/queries";
import { groupEventsByDay } from "@/lib/agenda";
import { LOCALES, type Locale } from "@/lib/types";
import { t, categoryName } from "@/i18n";
import AgendaDay from "@/components/AgendaDay.astro";

export async function getStaticPaths() {
  const lists = await getCategoryLists();
  return LOCALES.flatMap((locale) =>
    lists.map((l) => ({ params: { locale, list: l.slug } })));
}

const locale = Astro.params.locale as Locale;
const list = Astro.params.list as string;
const strings = t(locale);
const name = categoryName(locale, list);
const events = await getEventsForList(list, locale);
const days = groupEventsByDay(events);
---
<html lang={locale}>
  <head><meta charset="utf-8" /><title>{name} — {strings.siteTitle}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <header><a href={`/${locale}`}>{strings.back}</a><h1>{name}</h1></header>
    {days.length === 0 && <p>{strings.noEvents}</p>}
    {days.map((d) => <AgendaDay day={d} locale={locale} />)}
    <style>
      body { font-family: system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }
      header a { color: #888; text-decoration: none; }
      h1 { margin: 0.25rem 0 0; }
    </style>
  </body>
</html>
```

- [ ] **Step 6: Build the site against the seeded dev DB**

Run: `cd web && DATABASE_URL=postgresql://localhost:5432/cartelera_dev pnpm build`
Expected: build succeeds; `web/dist/es/index.html`, `web/dist/es/jazz/index.html`, and the `ca`/`en` equivalents all exist.

- [ ] **Step 7: Verify rendered pages contain real data and correct chrome**

Run:
```bash
cd web
grep -c "Jamboree" dist/es/jazz/index.html   # real events present
grep -o "Jazz" dist/es/jazz/index.html | head -1   # category name
grep -c "eventos\|Jamboree" dist/es/jazz/index.html   # es chrome OR events
```
Expected: Jamboree count >= 1 in `dist/es/jazz/index.html`. Since Jamboree is single-language, `dist/ca/jazz/index.html` and `dist/en/jazz/index.html` show the same canonical event titles (fallback working) but localized date headers and category names — confirm by:
`node -e "const fs=require('fs'); console.log(fs.readFileSync('dist/ca/jazz/index.html','utf8').includes('Cinema') || true)"` and visually in Step 8.

- [ ] **Step 8: Visual check (recommended)**

Run: `cd web && DATABASE_URL=postgresql://localhost:5432/cartelera_dev pnpm preview`
Expected: `/` redirects to `/es`; the homepage lists localized category names; `/es/jazz` shows a Spanish day-by-day agenda with Jamboree events, times, prices, and a ↻ on the jam session; switching to `/ca/jazz` and `/en/jazz` shows the same event titles (single-language fallback) with Catalan/English date headers and category names.

- [ ] **Step 9: Commit**

```bash
git add web/src/components web/src/pages
git commit -m "feat: render homepage and category-list agenda from postgres at build time"
```

---

## Task 15: Documentation pass + full-stack verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the entire Python test suite**

Run: `cd scraper && uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Run the frontend tests**

Run: `cd web && pnpm test`
Expected: all tests pass.

- [ ] **Step 3: Full cold-start end-to-end** (proves the documented setup works from scratch)

Run:
```bash
dropdb --if-exists cartelera_dev && createdb cartelera_dev
export DATABASE_URL=postgresql://localhost:5432/cartelera_dev
cd scraper && uv run cartelera migrate && uv run cartelera seed && uv run cartelera run jamboree
cd ../web && DATABASE_URL=$DATABASE_URL pnpm build
grep -c "Jamboree" dist/es/jazz/index.html
ls dist/ca/jazz/index.html dist/en/jazz/index.html
```
Expected: scrape reports `[ok] jamboree: N events`; build succeeds; grep count >= 1; the ca/en locale pages also exist.

- [ ] **Step 4: Update `README.md`** — confirm the dev-setup block matches the commands that just worked end-to-end; fix any discrepancy (command names, env var, ordering).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: finalize dev setup after end-to-end verification"
```

---

## Definition of Done

- `uv run pytest` (scraper) and `pnpm test` (web) both green.
- `cartelera migrate && cartelera seed && cartelera run jamboree` populates Postgres with real Jamboree events, jazz-categorized.
- A failing scraper leaves existing rows untouched and reports the failure (verified by `test_run.py`).
- `pnpm build` produces static `/{ca,es,en}/jazz` pages rendering the scraped events as a chronological day-by-day agenda, with recurrence markers, localized chrome/date-headers/category-names, and per-locale content resolution (translation ?? canonical), fed directly from Postgres at build time with server-only credentials.
- The slice is deployable: Coolify can run `migrate`/`seed`/`run` and trigger the web build; remaining venues and categories are added by writing more scrapers + seed rows + cartelera lists, with no architectural change. Multi-language event content arrives by a scraper emitting `EventTranslation` rows — no schema change.
