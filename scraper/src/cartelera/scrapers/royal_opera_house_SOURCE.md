# Royal Ballet and Opera (Royal Opera House) — source map

Venue slug: `royal-opera-house` (London) — Bow Street, Covent Garden
WC2E 9DD. Main stage and the Linbury Theatre are one venue. Categories
`classical` (opera, concerts) and `dance` (ballet), lists `classical` /
`dance` each whitelisted.

## Data source

`https://www.rbo.org.uk/tickets-and-events` (plain httpx,
`CARTELITA_BROWSER_HEADERS`): server-rendered React; the HTML embeds
`window.__REACT_QUERY_DEHYDRATED_STATE__ = {…}` (parse with
`json.JSONDecoder().raw_decode` from after the `=`). Query `eventsPage` →
`data.events` = `{events[103], tags[], locations[], bookingSeasons[],
onSaleDates[]}`. **All events are on one page** (`?page=2` returns the same
JSON).

Per event: `id`, `sourceType` (single-production-page / event-detail /
prismic-only-event-card…), `title`, `description` (HTML),
`productionPageUrl`, `performances[] {date, performanceType}`, `tags[]`
(ids), `locations[]` (ids), `isCancelled`, `isHiddenFromTicketsAndEvents`,
`imageResult`. Tag and location names come from the same JSON.

## Curation

1. `sourceType` = single-production-page with a `/production/…` page, not
   cancelled/hidden, not a cinema-season card (`?mode=cinema`). Drops the
   event-detail items (all tours, Tea Dance, Family Sundays) and the
   prismic-only cards (Ring cycle card duplicating its operas, Met Opera
   cinema, World Ballet Day online).
2. Tag "Opera and music" → classical, "Ballet and dance" → dance.
   Dropped when also tagged **Tours**, **Rehearsals** (Friends
   Rehearsals), **Talks and insights** (all Insights events), **Workshops
   and activities** (Barbie craft/storytelling). No genre tag → dropped
   (Dish from Waitrose filming event). "Cinema broadcasts", "School events",
   "Family Friendly" etc. are not curation (stage productions carry them
   too).
3. Location: the event's `locations` must include **Main Stage** (2) or
   **Linbury Theatre** (73). Dropped: Royal Opera House building-wide (0:
   Live at Lunch, Tea Dance), Crush Room (Recitals at Lunch), Clore Studio,
   Linbury Foyer, Thurrock, Cinema, Online only.
4. Performance: `performanceType` **standard** or **relaxed** (annotated
   "relaxed performance"). Dropped: schools-matinee, young-roh (Young RBO
   members only), hamlyn (Paul Hamlyn Club), focg (Friends), commercial,
   landp-*, guided-tour, thurrock.

## Fields

| Field | Source |
|---|---|
| `title` | event `title` (tags stripped) |
| `start_date`/`start_time` | performance `date` → Europe/London; past dates dropped |
| `external_id` | `<event id>@<YYYY-MM-DDTHH:MM>` (stable; performance ids exist only on the production page) |
| `source_url` | `https://www.rbo.org.uk` + `productionPageUrl` |
| `price` | production page (one request per kept production, ~34): its dehydrated state holds `stage-activity` items (id, `attributes.date`) and `activityAvailability` (id → `ticketsAvailable`, `minPriceAvailable`, `maxPriceAvailable`) → `format_gbp_range(min, max)` ("£47–273"), `ticketsAvailable` 0 → "sold-out", not on sale yet (no availability) → None. Matched on start time. The page's own "Ticket price" line is the production-wide min–max of the same numbers ("£10 - £199"). |
| `description` | event `description` (HTML → text) |
| `image_url` | `imageResult.desktopPath` |

## Verification

Last verified **2026-10-25** via HTTP cross-check: 312 performances (127
classical, 185 dance), 80% priced (the unpriced 20% are April–July 2027
performances not yet on sale), 23 sold out. Swan Lake: production page
lists 32 performances, 31 kept (one schools matinee); 31 Mar 2027 19:30
availability min 10 / max 199 → scraper "£10–199", page "Ticket price
£10 - £199". Carmen 29 Oct 19:00 "£23–343" (fixture). Cold-start DB: rows
= scraper output (see the batch report).
