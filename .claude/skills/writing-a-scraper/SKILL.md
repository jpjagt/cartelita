---
name: writing-a-scraper
description: Use when adding or repairing a venue scraper for Cartelera — a recon → author → verify procedure that uses the browser to find where each event field really lives, writes the scraper against a saved fixture with TDD, then cross-checks the output against the live site so no field is silently dropped.
---

# Writing (and verifying) a Cartelera scraper

A scraper that "runs" is not a scraper that "works." The Jamboree scraper passed
its tests while silently dropping price (missing for ~160 events) and mislabeling
club nights as jazz — because it parsed only the JSON-LD, which happens not to
carry price or category. The lesson: **verify the scraper's output against what a
human sees on the live page, field by field.** This skill is that discipline.

Each venue scraper is one module in `scraper/src/cartelera/scrapers/<venue>.py`
implementing the `Scraper` contract (`venue_slug` + `scrape() -> list[ScrapedEvent]`),
plus an offline test against a saved HTML fixture, plus a `SOURCE.md` recording
where each field comes from. Use `browser-use` (project skill) for recon and
verification.

## Checklist (create a TodoWrite item per phase)

1. Recon the site with the browser
2. Write the source map (`SOURCE.md`)
3. Author the scraper against a saved fixture (TDD)
4. Verify the output against the live site, field by field
5. Wire up seed + categories
6. Full cold-start end-to-end

## Phase 1 — Recon (browser-use)

Invoke the `browser-use` skill. The fast path is `browser-use open <url>` then
`browser-use eval "<js>"` to probe the DOM and inventory selectors — far faster
than guessing. (The daemon is occasionally flaky on first launch: if `open`
times out, run `browser-use close` and retry.)

Work top-down:

- **Homepage** → screenshot. How does the venue organize its programme? Section
  nav (e.g. "Concerts" vs "Disco") often maps to our top-level categories.
- **Find the events list.** Check the nav, `/sitemap.xml`, and common paths
  (`/agenda`, `/agenda/llista`, `/events`, `/programacio`). Prefer a **list/`llista`
  view** — it usually renders every event's fields in one page.
- **Inventory the data source.** In priority of robustness:
  1. An embedded **JSON blob** — `script[type="application/ld+json"]`,
     `__NEXT_DATA__`, or a state script. Robust, but **verify it carries every
     field you need** — JSON-LD frequently omits price and category (this was the
     Jamboree trap). Use it for what it has (clean ISO dates), not blindly.
  2. **Rendered DOM cards** — one element per event (`article`, `.event`, a card
     div) with child elements for each field. Probe with `eval`:
     ```
     browser-use eval "(()=>{const a=document.querySelectorAll('article'); return JSON.stringify({n:a.length, sample:a[0]?.outerHTML.slice(0,1500)})})()"
     ```
     then find the selectors for title, detail link, date/time, price, category
     tags. Measure coverage (e.g. how many of N cards have a `.price`) — low
     coverage is a smell that you're reading the wrong element.
- **Open one event-detail page** → screenshot + `eval`. Confirm which fields live
  ONLY on the detail page vs. the list. Prefer the list if it has everything
  (one request beats N).
- **Find the category discriminator.** It may be a section URL, a body class, or
  a tag. For Jamboree it's a tag: `+18` ⇒ `club`, else `jazz`. Genre/sub-genre
  tags that are too granular for our top-level categories go into the event's
  free-form `annotations` list, not `category_slugs`.

## Phase 2 — Source map (`SOURCE.md`)

Write `scraper/src/cartelera/scrapers/<venue>_SOURCE.md` recording, for this venue:
list URL(s); data source (JSON path or CSS selectors per field); the
category-mapping rule; the `external_id` source; and any quirks. This is the
artifact the future repair flow reads when the scraper breaks. Keep it short.
See the Jamboree scraper's module docstring for the level of detail.

## Phase 3 — Author against a fixture (TDD)

- Save the live list page to `scraper/tests/fixtures/<venue>_agenda.html`
  (`httpx.get(url, follow_redirects=True).text`). Tests run offline against this
  so they're deterministic.
- Implement `parse_<...>(html) -> list[ScrapedEvent]` as a **pure function**
  (HTML in, events out — no network) plus a thin `class <Venue>Scraper` whose
  `scrape()` fetches and delegates. End the module with `register(<Venue>Scraper())`.
- Emit fully-populated `ScrapedEvent`s: `title`, `start_date`, `source_url`,
  `category_slugs` (1+), and whatever else is available — `start_time`, `price`
  (free text, e.g. `"12€"`, `"s.o."`), `annotations` (genre tags etc.),
  `external_id`, `recurrence_hint`, `image_url`, `translations`.
- Honor the schema invariants: prices are **free text**, never parsed to numbers;
  the all-day sentinel (e.g. `00:00–23:59:59`) means "time unknown" → `None`;
  one row per occurrence (no recurrence expansion logic).
- Tests assert real properties: parses many events; every event has a valid
  date/title/url and a known category; **price coverage** (e.g. ≥90% have a
  price — this is the test that would have caught the original bug); the category
  discriminator works; annotations captured without the discriminator leaking in.
  Avoid brittle assertions pinned to volatile fixture data (don't assert
  `events[0]` is a specific dated event — find it by predicate).

## Phase 4 — Verify against the live site (the part people skip)

This is non-negotiable and is what distinguishes this skill from "just write a
scraper." Run the scraper live and **cross-check, field by field, against the
browser**:

- `uv run python -c "from cartelera.scrapers.<venue> import <Venue>Scraper; ..."`
  to print totals and per-field coverage (with price / with category / with
  annotations).
- Open the live list page in `browser-use`, `eval` to read the DOM's title / tags
  / price for the first ~6 events, and **compare to the scraper's output for the
  same events.** They must agree. A mismatch here is a real bug (this is exactly
  how the Jamboree price/category bugs were caught and confirmed fixed).
- Record the result + date in `SOURCE.md` ("last verified: YYYY-MM-DD").
- `browser-use close` when done.

## Phase 5 — Seed + categories

- If the scraper emits a category slug that isn't seeded, `run` fails fast with
  `unknown category slug '...'` (by design). Add the category to `seed.py`'s
  `CATEGORIES`.
- Add the venue to `seed.py` (idempotent get-or-create) with its full category
  set, and add it to the relevant cartelera category **lists**. For a
  **multi-category venue** (like Jamboree: jazz + club), add it to each list with
  that list's category as the **per-venue whitelist** (`whitelist_category_id`),
  so its events split into the right lists. A single-category venue can use a
  NULL whitelist (all events).
- Update `test_seed.py` to match.

## Phase 6 — Full cold-start end-to-end

Prove it from scratch:
```bash
dropdb --if-exists cartelera_dev && createdb cartelera_dev
export DATABASE_URL=postgresql://localhost:5432/cartelera_dev
cd scraper && uv run cartelera migrate && uv run cartelera seed && uv run cartelera run <venue>
# check category split + price coverage in psql
cd ../web && DATABASE_URL=$DATABASE_URL pnpm build
# confirm the venue's events render on the right category page(s) and NOT the wrong ones
```
Then run both test suites (`uv run pytest`, `pnpm test`) and commit.

## Anti-patterns (all real, all from the Jamboree pass)

- **Trusting JSON-LD blindly.** It looked clean and complete; it silently lacked
  price and category. Always verify the blob carries every field.
- **"Tests pass, ship it."** The fixture tests passed while two-thirds of prices
  were null. Coverage assertions + live cross-check catch this.
- **Title-keyword categorization.** "DJ" in the title is NOT a reliable club
  signal — two jazz concerts had a DJ warm-up. Use the venue's actual
  discriminator (the `+18` tag), not guesses about the title.
