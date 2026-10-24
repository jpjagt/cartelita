# Spektrix (shared helper `_spektrix.py`) — source map

Most London theatres, concert halls and arts centres sell through Spektrix.
Its v3 API is public and read-only: no key, no Cloudflare on the API host,
plain httpx with `CARTELITA_COMPAT_UA` (verified on ~45 London clients,
2026-10-24). Each venue module is thin: a `Client`, a `categorize(event)` on
the client's own attributes, and optionally a `Site` join and a venue split.

Base: `https://system.spektrix.com/<client>/api/v3` (most clients also answer
on a custom domain — `Client(name, host)`; either works).

## Endpoints

| Call | Use |
|---|---|
| `GET /events?instanceStart_from=<today>&instanceStart_to=<+183d>` | events: `id`, `name`, `description` (plain text) / `htmlDescription`, `imageUrl`, `webUrl` (usually empty), client-defined `attribute_*` |
| `GET /instances?startFrom=…&startTo=…` | **one row per performance**: `id`, `event.id`, `start` (venue-local, no tz), `cancelled`, `isOnSale`, `priceList.id`, `planId`, instance `attribute_*` (access flags) |
| `GET /instances/{id}/price-list` | prices: `amount`, `isBandDefault`, `ticketType.name`, `priceBand.name` |
| `GET /plans/{planId}` → `venue.id`; `GET /venues` | which building a performance is in (`plan_venues=True`) |

**Always send the date window**: unfiltered, the big clients (Barbican, Soho
Theatre) time out. Note the parameter names differ (`instanceStart_from` on
/events, `startFrom` on /instances).

## Fields

| Field | Source |
|---|---|
| `title` | event `name`, whitespace-collapsed (a venue may override, e.g. to strip internal season prefixes) |
| `start_date`/`start_time` | instance `start` (already Europe/London wall-clock) |
| `external_id` | instance `id` — one per performance, stable |
| `source_url` | the venue's own show page via the `Site` join; else event `webUrl`; else the client's public Spektrix event page `…/<client>/website/EventDetails.aspx?EventId=<numeric id>` (lists every performance with booking links; 200 to plain httpx) |
| `price` | price list → each band's **default** ticket type (`isBandDefault`: full price per seating band, so concession/member/access tiers don't widen the range) → `format_gbp_range` (2x rule: "£25", "£10–29.50"; all zero → "free"). One request per distinct price list, asked of on-sale instances first: an instance off sale (online booking closed, not yet released) answers **404**; up to 3 instances are tried, then the price stays unknown. |
| `description` | `description`, else the text of `htmlDescription` |
| `image_url` | `imageUrl` |
| `annotations` | instance boolean access flags that are true: Captioned, AudioDescribed, BSLInterpreted, Relaxed(Performance), Preview, PostShowTalk |
| `venue_slug` | multi-venue clients only: from an event attribute (room) or the performance's plan → client venue |

Cancelled instances are dropped.

## Curation — the API is the box office, not the programme

The API carries everything the box office sells: ice-cream pre-orders, "Secure
My Booking", touch tours, workshops, courses, CPD days, test events, staff
lunches, hires. **Every venue must filter on one of the client's own
attributes** (`Type`, `EventType`, `WebsiteFilterCategory1`, `Genre`,
`PrimaryArtForm`…; names differ per client — look at
`docs/london-research/` and at a live `/events` response), never on title
keywords. Where a client has no usable label (e.g. Royal Court: only a room
field, and test events/touch tours sit in the main rooms), use
`Site(required=True)`: only events the venue lists on its own website are
kept.

## The `Site` join

`Site(listing_url, link_pattern)`: fetch the venue's what's-on page, follow
every absolute link matching `link_pattern` (one show page each), and collect
the Spektrix ids each page embeds — full ids (`571766ANTDSK…`, Polka) or the
numeric ids of booking links (`/book/543497`, Little Angel;
`EventInstanceId=…`). An event's page is the one carrying the most of its
event/instance ids (a page's "you may also like" links never outnumber its
own). Costs one request per show page. A site whose pages embed no Spektrix
ids (Soho Theatre) can't be joined; its events link to the Spektrix event
page.

## Venues on this helper

| Module | Client | Curation |
|---|---|---|
| `polka.py` | `polka` | `Type` = Show; site join |
| `little_angel_theatre.py` | `littleangeltheatre` | `EventType` = In-house show; plan venues (Theatre / Studios); site join |
| `soho_theatre.py` | `sohotheatre` | `Venue` room → Dean Street / Walthamstow; `WebsiteFilterCategory1` Theatre → theater, Family → kids |
