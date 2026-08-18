# Ulikhanyan Club — source map

Jazz club, 7 Sayat-Nova Ave, Yerevan. Live jazz/fusion/funk/ethno-jazz daily.

## Source choice

The venue's **own site** (`ulikhanyanclub.com`, powered by the Haytoms.am
ticketing platform) is the source. It server-renders the full upcoming agenda
(~a rolling week, one concert per day) with date, time, image and description —
no JS needed. The aggregator alternatives (esora.app, tomsarkgh.am) were not
needed: the own site + the Haytoms ticket API already carry every field,
including per-seat prices, and are one hop closer to the truth.

## List page

- `https://ulikhanyanclub.com/en/buy-ticket` — every upcoming event as a
  Bootstrap `div.row` card inside `.event-area`. The homepage `/en` shows the
  same cards; the dedicated page is used. `/arm` carries **identical** content
  (titles are Latin, descriptions unchanged), so there are no translations to
  scrape.

## Per-field mapping (list page)

| field        | where |
|--------------|-------|
| title        | `h4.event-name a` text |
| external_id  | numeric id in the anchor href `en/buy-ticket/<id>` — one id per **occurrence** (each concert night has its own page), so it's a safe dedup key |
| source_url   | `https://ulikhanyanclub.com/en/buy-ticket/<id>` |
| date + time  | `.event-fee2` text, e.g. `18  Օգոստոս  Երեքշաբթի 20:30` — day, **Armenian month name (also on the EN page)**, Armenian weekday, HH:MM. **No year** → resolved to the candidate year (prev/this/next) closest to `today` (the list only spans the coming days) |
| description  | the card's `<p>` (artist lineup, often bilingual hy/en) |
| image_url    | `.event-feature2 img[src]` (hosted on `api.haytoms.am`) |
| price        | NOT on the site pages at all — see ticket API below |
| category     | always `jazz` (single-genre venue, no discriminator) |
| language     | None — instrumental concerts, the source states nothing |
| recurrence   | the weekly jam session titles itself `... EVERY MONDAY` → `recurrence_hint` |

## Price: Haytoms ticket API

Each card carries `button[data-openticket=<ticket_id>]` and the page embeds
`var haytoms_token = "<JWT>"` (short-lived, group_id 17). The widget's own call
is replicated:

```
POST https://api.haytoms.am/get/ticket
Auth: HaytomsToken <token from the page>
id=<ticket_id>
```

The JSON response's `map.Levels[].Places[]` is the seat map; every seat has an
integer `Price` (AMD — `event_currency` is empty = default) and an `active`
flag (seat still buyable). Price rule: no active seats → `"sold-out"`; all
prices 0 → `"free"`; else single tier → `"<hi> AMD"`, range only when
hi ≥ 2×lo. As of 2026-08 every night is a flat 5000 AMD (jam session 3000 AMD).
A failed API call leaves that event's price `None` rather than aborting.

## Quirks

- The `.event-fee2` time is the **ticketing** time (doors ~20:30); one August
  description says "at 9 PM" while fee2 says 20:30 — the structured fee2/API
  `timeline` value is what we surface.
- The page embeds **two different** Instagram handles (one near the top,
  one in the footer): `ulikhanyanjazzclub` and `ulikhanyanartclub`. Verified
  live (WebSearch/WebFetch) which is the real active account: `ulikhanyanjazzclub`
  has 8.9k followers, bio "Yerevan's home of live jazz - since 2008 • Jam
  Sessions every Monday" (matches our scraped recurrence_hint), phone matching
  the site, and links back to `ulikhanyanclub.com`. `ulikhanyanartclub` yields
  no retrievable profile content — likely stale/wrong. Use `ulikhanyanjazzclub`.
- Fixture: `tests/fixtures/ulikhanyan_club_agenda.html` (captured 2026-08-18,
  8 events Aug 18–25) + two `get/ticket` payloads (13940 @5000, 13946 jam @3000).

## Verification

`browser-use` was unavailable during verification: the installed CLI had been
upgraded to an incompatible major version (`browser-harness` 0.1.9, no
`--session`/`open`/`eval` commands) whose local daemon requires an interactive
Chrome "Allow remote debugging" click no agent could perform, and no cloud auth
was configured for an isolated remote daemon. Substituted an independent
cross-check: fetched the live `/en/buy-ticket` page fresh via `httpx` (not the
fixture, not through the scraper's own parse function) and hand-inspected it
with a throwaway BeautifulSoup script — all 8 events' title/date-time/href/
image/ticket-id matched `UlikhanyanClubScraper().scrape()`'s live output
exactly. Independently POSTed the Haytoms ticket API for a third event
(id 13941, not in the fixture) and confirmed `price_from_ticket` returns
"5000 AMD", consistent with the flat-price pattern.

Last verified against the live site: 2026-08-18 (8/8 events, field-by-field,
via raw HTTP cross-check in lieu of browser-use — see above).
