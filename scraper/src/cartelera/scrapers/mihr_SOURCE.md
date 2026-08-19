# Mihr Theatre — source map

> **DORMANCY NOTE:** as of 2026-08-19 the esora.app feed for this venue is
> **verified empty** (`eventOccurrenceIds: []`, 0 upcoming events). Mihr
> Theatre is a touring contemporary-dance company (no fixed venue) that
> announces performances on Instagram/Facebook; esora ingests those posts, so
> the feed is expected to **repopulate on its own** once the company posts
> its next show. Registering this scraper now, while the feed is dormant, is
> **intentional**: the nightly `cartelera run` becomes the re-check. No code
> change will be needed when events return — they'll simply start appearing
> in the next run.

## Why Esora, not the venue's own site

- Mihr Theatre **does** have a live official website, `mihrtheatre.com`
  (confirmed HTTP 200 on 2026-08-19) — kept as `site_url` for reference/link,
  but it is not scraped: it's a company/portfolio site with no discoverable
  structured events calendar, and esora already provides one.
- **esora.app** runs a dedicated Mihr Theatre source page
  (`https://esora.app/en/yerevan/sources/82d1073c-6107-4dfd-b14e-533c0bcd29c9`),
  the same Instagram-ingestion pattern as `malkhas_jazz_club.py` /
  `kami_club.py` / `pantomime_theatre.py`. This is the only per-date listing
  found for the company; chosen even though it's currently empty, for the
  reason above.

## Data source: Esora's public JSON API (shared plumbing, see `esora.py`)

```
GET https://esora.app/api/events/feed?eventSourceId=82d1073c-6107-4dfd-b14e-533c0bcd29c9&limit=100&page=N
```

This scraper is a thin wrapper (`mihr.py`) over the shared `EsoraFeedScraper`
/ `parse_feed` in `esora.py` — see `malkhas_jazz_club_SOURCE.md` /
`kami_club_SOURCE.md` for the full response shape and field-by-field
discovery story (identical here). What's specific to this venue:

| field | value |
|---|---|
| `EVENT_SOURCE_ID` | `82d1073c-6107-4dfd-b14e-533c0bcd29c9` |
| category | fixed `dance` — Mihr is a contemporary dance company; no genre split needed |
| excluded tags | none beyond the helper's default (empty) — the feed has no upcoming events to inspect for a blanket tag; re-check once it repopulates |
| address | `None` — Mihr is a **touring company with no fixed venue**; the esora source page's embedded `places` entity is empty (`"places":{"ids":[],"entities":{}}}`), confirming there is no fixed address to report, not a scraper omission |
| instagram_url | `https://www.instagram.com/mihrtheatre` — from the esora source page's `instagramUsername`/JSON-LD `sameAs` fields |
| site_url | `https://mihrtheatre.com` — confirmed live (HTTP 200) |

## Verification, 2026-08-19

HTTP-first (browser-use unavailable per repo policy — see AGENTS.md gotchas);
verified with `curl`/`httpx`:

1. `GET https://esora.app/api/events/feed?eventSourceId=82d1073c-6107-4dfd-b14e-533c0bcd29c9&limit=100&page=1`
   → **HTTP 200**, body `{"result":{"eventOccurrenceIds":[],"pagination":{"page":1,"limit":100,"total":0,"totalPages":0}},"entities":{}}`
   — confirms the feed is live and reachable, and confirms it is empty (not
   an error or a 404 masquerading as empty).
2. `GET https://esora.app/en/yerevan/sources/82d1073c-6107-4dfd-b14e-533c0bcd29c9`
   (the human-facing source page, server-rendered Next.js RSC payload) →
   HTTP 200; embedded state confirms `instagramUsername: "mihrtheatre"` and
   an empty `places` entity and `eventOccurrenceIds` list, matching the API
   response — the page and the API agree, so the emptiness is real, not a
   scraper bug.
3. `GET https://mihrtheatre.com` → HTTP 200, confirms `site_url` resolves.
4. `uv run cartelera dry-run mihr` → `[dry-run] mihr: 0 events`, exit 0, no
   traceback — confirms the scraper itself runs cleanly end-to-end against
   the live (empty) feed.

Coverage: since the live feed has zero upcoming events, there is nothing to
field-check against a live event card today. `parse_feed`'s correctness on a
populated feed is covered by `tests/test_mihr.py`'s synthetic populated
fixture and by `tests/test_esora.py`'s exhaustive coverage of the shared
parsing/dedup logic (identical code path, parametrized only by
category/excluded-tags/event-source-id — see `esora.py`).
