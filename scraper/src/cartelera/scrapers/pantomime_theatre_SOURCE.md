# Yerevan State Pantomime Theatre — source map

> **DORMANCY NOTE:** as of 2026-08-19 the esora.app feed for this venue is
> **verified empty** (`eventOccurrenceIds: []`, 0 upcoming events; ~10
> lifetime events total per esora's own count). The theatre announces
> exclusively on Instagram/Facebook; esora ingests those posts, so the feed
> is expected to **repopulate on its own** once the theatre resumes posting
> (likely September, after the summer off-season — Armenian state theatres
> typically run a September–June season). Registering this scraper now, while
> the feed is dormant, is **intentional**: the nightly `cartelera run`
> becomes the re-check. No code change will be needed when events return —
> they'll simply start appearing in the next run. If the feed is *still*
> empty well past September, that's worth a manual look, not a bug in this
> scraper.

## Why Esora, not the venue's own site

- The theatre's own website is **dead** (no resolving site found under any
  obvious pantomime-theatre domain as of 2026-08-19) — per the task brief,
  `site_url=None`.
- **esora.app** runs a dedicated Pantomime Theatre source page
  (`https://esora.app/en/yerevan/sources/17432552-b94e-41c7-8401-855e688d6a62`),
  the same Instagram-ingestion pattern as `malkhas_jazz_club.py` /
  `kami_club.py`. This is the only per-date listing found for the venue;
  chosen even though it's currently empty, for the reason above.

## Data source: Esora's public JSON API (shared plumbing, see `esora.py`)

```
GET https://esora.app/api/events/feed?eventSourceId=17432552-b94e-41c7-8401-855e688d6a62&limit=100&page=N
```

This scraper is a thin wrapper (`pantomime_theatre.py`) over the shared
`EsoraFeedScraper` / `parse_feed` in `esora.py` — see
`malkhas_jazz_club_SOURCE.md` / `kami_club_SOURCE.md` for the full response
shape and field-by-field discovery story (identical here). What's specific
to this venue:

| field | value |
|---|---|
| `EVENT_SOURCE_ID` | `17432552-b94e-41c7-8401-855e688d6a62` |
| category | fixed `theater` — the venue is a pantomime theatre; no genre split needed |
| excluded tags | none beyond the helper's default (empty) — the feed has no upcoming events to inspect for a blanket tag; re-check once it repopulates |
| address | `21 Gevorg Kochar St, Yerevan 0001, Armenia` — from the esora source page's embedded `places` entity (`name: "Yerevan State Pantomime Theatre"`), the only address source found; not guessed |
| instagram_url | `https://www.instagram.com/pantomime_theatre` — from the esora source page's `instagramUsername`/JSON-LD `sameAs` fields |
| site_url | `None` — no live official website found |

## Verification, 2026-08-19

HTTP-first (browser-use unavailable per repo policy — see AGENTS.md gotchas);
verified with `curl`/`httpx`:

1. `GET https://esora.app/api/events/feed?eventSourceId=17432552-b94e-41c7-8401-855e688d6a62&limit=100&page=1`
   → **HTTP 200**, body `{"result":{"eventOccurrenceIds":[],"pagination":{"page":1,"limit":100,"total":0,"totalPages":0}},"entities":{}}`
   — confirms the feed is live and reachable, and confirms it is empty (not
   an error or a 404 masquerading as empty).
2. `GET https://esora.app/en/yerevan/sources/17432552-b94e-41c7-8401-855e688d6a62`
   (the human-facing source page, server-rendered Next.js RSC payload) →
   HTTP 200; embedded state confirms `name: "Yerevan State Pantomime
   Theatre"`, the address and Instagram fields above, and an empty
   `eventOccurrenceIds` list matching the API response — the page and the API
   agree, so the emptiness is real, not a scraper bug.
3. `uv run cartelera dry-run pantomime_theatre` → `[dry-run]
   pantomime-theatre: 0 events`, exit 0, no traceback — confirms the scraper
   itself runs cleanly end-to-end against the live (empty) feed.

Coverage: since the live feed has zero upcoming events, there is nothing to
field-check against a live event card today. `parse_feed`'s correctness on a
populated feed is covered by `tests/test_pantomime_theatre.py`'s synthetic
populated fixture and by `tests/test_esora.py`'s exhaustive coverage of the
shared parsing/dedup logic (identical code path, parametrized only by
category/excluded-tags/event-source-id — see `esora.py`).
