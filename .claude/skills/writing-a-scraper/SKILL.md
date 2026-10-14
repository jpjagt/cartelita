---
name: writing-a-scraper
description: Use when adding or repairing a venue scraper for Cartelera — an HTTP-first recon → author → verify procedure that finds where each event field really lives, writes the scraper against a saved fixture with TDD, then cross-checks the output against the live site so no field is silently dropped.
---

# Writing (and verifying) a Cartelera scraper

A scraper that "runs" is not a scraper that "works." The Jamboree scraper passed
its tests while silently dropping price (missing for ~160 events) and mislabeling
club nights as jazz — because it parsed only the JSON-LD, which happens not to
carry price or category. The lesson: **verify the scraper's output against what a
human sees on the live page, field by field.** This skill is that discipline.

Each scraper is one module in `scraper/src/cartelera/scrapers/<venue>.py`
implementing the `Scraper` contract (`scrape() -> list[ScrapedEvent]`; by
convention single-venue scrapers also carry a `venue_slug` attribute), plus an
offline test against a saved HTML fixture, plus a `SOURCE.md` recording where
each field comes from. Recon and verification are HTTP-first (see Phase 1);
the browser is a fallback for JS-only sites.

A scraper registers as a **source**. The common case is one venue's own site:
end the module with `register(<Venue>Scraper(), venue)` and the venue slug is
the source slug. A **multi-venue source** (an aggregator site, a social-media
profile feeding several venues) instead uses `register_source(scraper,
SourceDefinition(slug=..., name=..., venues=[...]))` and must set `venue_slug`
on every ScrapedEvent; the source's venue list is its editorial whitelist — the
runner fails fast on events for any venue outside it. Everything below applies
either way; `<venue>` then means the source.

## Checklist (create a TodoWrite item per phase)

1. Recon the site (HTTP-first)
2. Write the source map (`SOURCE.md`)
3. Author the scraper against a saved fixture (TDD)
4. Verify the output against the live site, field by field
5. Wire up seed + categories
6. Full cold-start end-to-end

## Phase 1 — Recon (HTTP-first; browser only if the site demands it)

**Start with plain HTTP** (`httpx.get`, a desktop User-Agent header if needed):
most venue/aggregator sites are server-rendered, and for those raw HTML ≡
rendered DOM, so `httpx` + BeautifulSoup probing answers everything the browser
would — faster and parallel-safe. Also probe for structured back-ends before
scraping HTML: an events SPA usually has a JSON API one `curl` away (check
`page-data.json`, `/api/...` paths, `__NEXT_DATA__`, RSC flight data — e.g.
esora.app exposes `GET /api/event-sources?city=<city>&limit=500` and
`GET /api/events/feed?eventSourceId=...`, the source behind several Yerevan
scrapers).

**When httpx comes back without the events** (few links/cards, an empty shell,
a 403 or challenge page), run the recon tool from `scraper/`:

```bash
uv run python tools/recon.py <list-url> [--scroll] [--click SEL]... [--wait MS] [--dump DIR]
```

It reports, in a few hundred tokens: whether httpx / curl_cffi get the page,
server- vs JS-rendered, and a ranked list of candidate data sources — XHR/fetch
JSON (with method, POST body, structure sketch, sample) and embedded state
(`__NEXT_DATA__`, Nuxt, RSC, JSON-LD, Astro props, `data-*` JSON). Then fetch
the top candidate **with httpx** and confirm it carries every field you need
(it's a candidate, not a verdict). `--scroll`/`--click` trigger lazy loads and
load-more buttons. One-time setup: `uv run playwright install
chromium-headless-shell`.

**Browser only via `tools/recon.py`** — it launches its own isolated headless
Chromium (parallel-safe). NEVER attach to the user's personal Chrome. For an
interactive flow recon can't drive (multi-step filters, date pickers), use
`playwright-cli -s=<venue> …` (a named, isolated session) with `requests
--filter <substring>`, redirecting response bodies to files — `response-body`
inlines the whole body into your context. If the site is truly browser-only,
report the blocker instead of working around it (a scraper that only works in
a browser can't run in production anyway).

- **Bot protection** (403 / Cloudflare "Just a moment..." with httpx even with
  a browser UA): try `curl_cffi.requests.get(url, impersonate="chrome")` (or
  `cartelera.scrapers.http.fetch(url, impersonate=True)`) — a valid production
  client (it's a runtime dependency). recon.py's verdict says which client
  works; record the client in `SOURCE.md`.

Work top-down:

- **Homepage** → fetch and skim. How does the venue organize its programme?
  Section nav (e.g. "Concerts" vs "Disco") often maps to our top-level categories.
- **Find the events list.** Check the nav, `/sitemap.xml`, and common paths
  (`/agenda`, `/agenda/llista`, `/events`, `/programacio`). Prefer a **list/`llista`
  view** — it usually renders every event's fields in one page.
- **Inventory the data source.** In priority of robustness:
  1. An embedded **JSON blob** — `script[type="application/ld+json"]`,
     `__NEXT_DATA__`, or a state script. Robust, but **verify it carries every
     field you need** — JSON-LD frequently omits price and category (this was the
     Jamboree trap). Use it for what it has (clean ISO dates), not blindly.
  2. **Server-rendered cards** — one element per event (`article`, `.event`, a
     card div) with child elements for each field. Probe the fetched HTML with
     BeautifulSoup (`select`/`select_one` in a scratch script) to find the
     selectors for title, detail link, date/time, price, category tags. Measure coverage (e.g. how many of N cards have a `.price`) — low
     coverage is a smell that you're reading the wrong element.
- **Fetch one event-detail page** and probe it the same way. Confirm which
  fields live ONLY on the detail page vs. the list. Prefer the list if it has everything
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
  (free text, e.g. `"12€"`, `"s.o."`), `language` (display-only free text on
  the price convention: exactly what the source states — `"VOSE"`, `"hy"`,
  `"non-verbal"` — `None` when unstated, never inferred), `annotations` (genre
  tags etc.), `external_id`, `recurrence_hint`, `image_url`, `translations`.
  Multi-venue sources also set `venue_slug` on every event.
- Honor the schema invariants: prices are **free text**, never parsed to numbers;
  the all-day sentinel (e.g. `00:00–23:59:59`) means "time unknown" → `None`;
  one row per occurrence (no recurrence expansion logic).
- **`external_id` is the per-OCCURRENCE dedup key**, not "the venue's id for the
  thing." The upsert dedups on `(venue, external_id)` and one Event row is one
  occurrence — so if the venue's natural id is *coarser* than an occurrence (a
  film slug that screens on many dates, a series id with multiple sessions),
  qualify it with date+time (e.g. `f"{slug}@{date}T{HHMM}"`). A bare coarser id
  silently collapses occurrences — later screenings overwrite earlier ones (this
  was the Filmoteca trap: June 2's Spione/Wendy clobbered by later-week
  screenings of the same films). The upsert now *raises* on duplicate
  `external_id` within one batch, so a per-occurrence-uniqueness test catches it.

## Price convention

The `price` field must be one of:
- `None` — price unknown or not scrape-able
- `"free"` — no admission cost (normalize locale-specific phrases: "Entrada gratuita", "Activitat gratuïta", "entrada libre", price==0, etc.)
- `"sold-out"` — tickets exhausted (normalize: "s.o.", "Sold Out", etc.)
- A concise display string — informative and short. Prefer a plain value like `"10€"` or `"10–22€"`. Skip member-tier and discount prices.

When a price string contains multiple values (member prices, promo discounts), extract the main/highest public price.

**Only show a range when the tiers differ meaningfully for the user.** Rule of
thumb: if the high price point is **< 2× the low** (e.g. 7€ vs 9€), the spread is
minor — don't emit a range; pick a single price in the scraper logic. Two ways to
collapse it, in order of preference:
- If each occurrence carries a signal for which tier applies (e.g. its date, when
  weekday/weekend pricing differs), pick the **applicable tier per event** — more
  accurate than a flat value. Cinemes Girona does this: `7€` weekdays, `9€`
  weekends, keyed off each occurrence's `start_date.weekday()`.
- Otherwise pick the **highest** public price across the tiers. Cines Verdi does
  this in `_format_price` (`max(cents)`).
Reserve a `"x–y€"` range for genuinely large, user-relevant spreads (high ≥ 2×
low) — e.g. concert halls with real seating tiers (L'Auditori, Palau de la
Música). When you have an integer-euro `(lo, hi)`, format it with the shared
`cartelera.scrapers.price.format_eur_range(lo, hi)` helper — it applies this 2×
rule for you (range only when `hi >= 2*lo`, else `"{hi}€"`). Don't hand-roll
`f"{lo}–{hi}€"`. Armenian dram uses the same rules with the symbol convention
(`"5000֏"`, range `"2500–5000֏"`): `format_amd_range(lo, hi)` for numeric
bounds, `normalize_amd(text)` for source free text ("5000 AMD" → "5000֏") —
never emit the "AMD" unit in output.
- Tests assert real properties: parses many events; every event has a valid
  date/title/url and a known category; **price coverage** (e.g. ≥90% have a
  price — this is the test that would have caught the original bug); the category
  discriminator works; annotations captured without the discriminator leaking in.
  Avoid brittle assertions pinned to volatile fixture data (don't assert
  `events[0]` is a specific dated event — find it by predicate).

## Phase 4 — Verify against the live site (the part people skip)

This is non-negotiable and is what distinguishes this skill from "just write a
scraper." Run the scraper live and **cross-check, field by field, against an
INDEPENDENT read of the live site**:

- `uv run python -c "from cartelera.scrapers.<venue> import <Venue>Scraper; ..."`
  to print totals and per-field coverage (with price / with category / with
  annotations).
- Fetch the live list page FRESH (httpx, not the fixture, not through the
  scraper's own code path) and extract title / tags / price for the first ~6
  events with throwaway parsing logic written independently of the scraper —
  **compare to the scraper's output for the same events.** They must agree. A
  mismatch here is a real bug (this is exactly how the Jamboree price/category
  bugs were caught and confirmed fixed). For a server-rendered site this is
  equivalent to (and stricter than) eyeballing the browser DOM; if the site is
  JS-rendered, verify against its underlying JSON API instead, or against the
  rendered DOM from `uv run python tools/recon.py <url> --dump DIR`
  (`DIR/rendered.html`) parsed with throwaway BeautifulSoup.
- Record the result + date + method in `SOURCE.md` ("last verified: YYYY-MM-DD
  via HTTP cross-check").

## Phase 5 — Seed + categories

- If the scraper emits a category slug that isn't seeded, `run` fails fast with
  `unknown category slug '...'` (by design). Add the category to `seed.py`'s
  `CATEGORIES`.
- Same for cities: a venue definition whose `city_slug` isn't in `seed.CITIES`
  fails fast in seed. A genuinely new city also needs a `web/src/lib/cities.ts`
  entry (locales, defaults) and i18n dictionaries; adding a venue to an
  existing city needs nothing there. (Lists are per-city — slugs like "jazz"
  exist once per city — but seed handles that automatically.)
- Update `test_seed.py` to match.
- Any changes made to these files should be reported in your final message.

## Phase 6 — Full cold-start end-to-end

Prove it from scratch — but **NEVER drop `cartelera_dev`**: that is the user's real
local dev database, not a throwaway. Use a dedicated, clearly-named scratch DB for
the cold-start so you never touch the user's data. (`migrate` auto-creates the DB
if it doesn't exist, so no manual `createdb` is needed.)
```bash
export DATABASE_URL=postgresql://localhost:5432/cartelera_<venue>
cd scraper && uv run cartelera migrate && uv run cartelera seed && uv run cartelera run <venue>
# check category split + price coverage in psql
# AND count events per day — they must match the live site. A row count far below
# the live total means external_ids collapsed occurrences (see Phase 3); the
# parser tests won't see this because the upsert is where it happens.
cd ../web && DATABASE_URL=$DATABASE_URL pnpm build
# confirm the venue's events render on the right category page(s) and NOT the wrong ones
dropdb --if-exists cartelera_<venue>   # the scratch DB is yours to drop; cartelera_dev is NOT
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
- **Coarse `external_id` that collapses occurrences.** Filmoteca's film slug is
  shared across every screening of a film; using it bare made the upsert overwrite
  earlier screenings with later ones (115 occurrences → 66 rows). Qualify the id
  with date+time. Invisible in parser tests — caught only by per-day DB counts and
  the new duplicate-id guard in the upsert.
