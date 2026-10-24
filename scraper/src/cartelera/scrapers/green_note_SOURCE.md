# Green Note — source map

Venue slug: `green-note` (London) — 106 Parkway, Camden NW1 7AN.
Category `folk` (list `folk`): a single-genre folk/roots/americana venue.

## Data source

WordPress with the "Theater for WordPress" plugin (no REST type for its
events), plain httpx with `CARTELITA_BROWSER_HEADERS`; robots allows all.

- **Listing** `https://www.greennote.co.uk/events-page/` (one page, 174
  events on 2026-10-25), one `.wp_theatre_event` per event:
  `.wp_theatre_event_title a` (title + production page), 
  `.wp_theatre_event_datetime` ("Mon 26th October" — no year, no time),
  `.wp_theatre_event_venue` (room), `.wp_theatre_event_remark`,
  `.wp_theatre_event_tickets_url` (WeGotTickets / liveit),
  `.wp_theatre_event_prices` ("£ 15.00"), `.wp_theatre_event_tickets_status`
  (`…_status_cancelled` "Cancelled").
- **Production pages** (`/production/<slug>/`, one request per kept
  production, ~150, ~30 KB gzipped each): their own `.wp_theatre_event`
  blocks read "Tue 27th October 7:00pm" — the only place the start time
  is stated.
- (`/upcoming_events` RSS has the year but neither time, room nor price.)

## Curation

Rooms **GREEN NOTE** (upstairs) and **THE BASEMENT BAR** (downstairs,
annotated "Basement Bar") are the venue. Dropped by room: Green Note
Presents shows elsewhere — THE WATER RATS (9), ST PANCRAS OLD CHURCH (3),
HEATH ST BAPTIST CHURCH (1), THE LEXINGTON (1, owned by its DICE source),
and no room (3). Cancelled events dropped.

## Fields

| Field | Source |
|---|---|
| `title` | listing title (promoter prefixes like "Folk and Roots Presents:" are the venue's own) |
| `start_date` | listing date; year from the weekday (`_yearless`, anchored on today) |
| `start_time` | production page block for that date; unknown if the page fails |
| `price` | listing price → `gbp_price` ("£ 12.50" → "£12.50"); status "Sold out" → "sold-out" |
| `description` | listing remark |
| `source_url` | production page |
| `external_id` | `<production slug>@<date>` (`#n` suffix if a production has two rows that day) |

## Verification

Last verified **2026-10-25** via HTTP cross-check with production pages:
157 events, 100% priced, 100% timed. Malin Pettersen — page "GREEN NOTE
Sun 25th October 7:00pm £ 18.00" → 25 Oct 19:00 "£18"; Claire Watts —
"THE BASEMENT BAR Sun 25th October 7:30pm £ 13.00" → 19:30 "£13" [Basement
Bar]; Josh Flowers — "Thu 7th January 7:00pm £ 15.00" → 7 Jan **2027**
19:00 "£15". Cold-start DB: rows = scraper output (see the batch report).
