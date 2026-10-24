# Spektrix (shared helper `_spektrix.py`) — source map

Most London theatres, concert halls and arts centres sell through Spektrix.
Its v3 API is public and read-only: no key, no Cloudflare on the API host,
plain httpx with `CARTELITA_COMPAT_UA` (verified on ~45 London clients,
2026-10-24). Each venue module is thin: a `Client`, a `categorize(event)` on
the client's own attributes, and optionally a `Site` join, a venue split and
the hooks below — one `spk.scrape(...)` call.

Base: `https://system.spektrix.com/<client>/api/v3` (most clients also answer
on a custom domain — `Client(name, host)`; either works).

## Endpoints

| Call | Use |
|---|---|
| `GET /events?instanceStart_from=<today>&instanceStart_to=<+183d>` | events: `id`, `name`, `description` (plain text) / `htmlDescription`, `imageUrl`, `webUrl` (usually empty), client-defined `attribute_*` |
| `GET /instances?startFrom=…&startTo=…` | **one row per performance**: `id`, `event.id`, `start` (venue-local, no tz), `cancelled`, `isOnSale`, `priceList.id`, `planId`, instance `attribute_*` (access flags) |
| `GET /instances/{id}/price-list` | prices: `amount`, `isBandDefault`, `ticketType.name`, `priceBand.name` |
| `GET /plans/{planId}` → `name`, `venue.id`; `GET /venues` | which building (and seating plan) a performance is in (`plan_venues=True`) |

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
| `price` | price list → (the venue's `price_bands` filter) → each band's **default** ticket type (`isBandDefault`: full price per seating band, so concession/member/access tiers don't widen the range) → `format_gbp_range` (2x rule: "£25", "£10–29.50"; all zero → "free"). One request per distinct price list, asked of on-sale instances first: an instance off sale (online booking closed, not yet released) answers **404**; up to 3 instances are tried, then the price stays unknown. |
| `description` | `description`, else the text of `htmlDescription` |
| `image_url` | `imageUrl` |
| `annotations` | instance boolean flags that are true (`ACCESS_FLAGS`: captioned, audio described, BSL interpreted, relaxed, sensory adapted, chilled, autism/dementia friendly, parent and baby, touch tour, preview, post-show talk — each under the several names clients use), then the text of the client's free-text attributes the module names in `annotation_attrs` (e.g. "Captioned Screening"); deduplicated. Only performance-facing labels — never press/writers' nights, schools flags, discounts or internal notes |
| `venue_slug` | multi-venue clients only: from an event attribute (room) or the performance's plan → client venue (`instance["venue"]`, plus the plan's own name in `instance["plan"]`) |

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

`Site(listing_url, link_pattern)`: fetch the venue's listing page(s) —
`listing_url` may be a tuple (Kiln: what's-on + cinema listings) and may be
a `sitemap.xml` (Royal Court, RAM: its `<loc>`s are absolute links) — follow
every link fully matching `link_pattern` (absolute, or a relative `href`
resolved against its listing page; one show page each), and collect the
Spektrix ids each page embeds (`embedded_ids`): full ids (`571766ANTDSK…`,
Polka) or the numeric ids of booking links — `/book/<id>` (Little Angel),
`/book/instance/<id>` (The Place), `/book-online/<id>` (Brixton House),
`/tickets/<id>` (CPT), `EventInstanceId=…`. An event's page is the one
carrying the most of its event/instance ids (a page's "you may also like"
links never outnumber its own). Costs one request per show page. A listing
that fails fails the run; a show page that fails (a dead link) is skipped
with a warning. `required=True` makes the join curation: only listed events
are kept. A module that fetches the show pages itself (because it reads
more from them, e.g. Brixton House's stated price) passes `page_ids=`
(page URL → `embedded_ids(html)`) instead. A site whose pages embed no
Spektrix ids (Soho Theatre) can't be joined; its events link to the
Spektrix event page. A paginated listing of unknown length isn't a `Site`
(Barbican pages its own).

## Hooks (`spk.scrape` keyword arguments)

| Hook | What | Used by |
|---|---|---|
| `title(event)`, `url(event)` | event name / page override | Arcola, Brixton, The Place (titles); Barbican, Cecil Sharp (both); Cadogan (`webUrl`) |
| `venue(event, instance)` | our venue slug, None drops the performance | multi-venue sources, building filters |
| `plan_venues=True` | `instance["venue"]` (client venue record) + `instance["plan"]` (`{"name"}`) from the seating plan | Little Angel, Arcola, Orange Tree, CPT, Southwark, Theatre503 (plan name), RAM, RCM, Cecil Sharp, Barbican |
| `prepare(events, instances)` | the venue's own pass over the programme before curation | Blackheath (category from instances), Cecil Sharp (efdss.org listing join) |
| `price_bands(price)` | price-list entry filter before the band-default rule; when it keeps no paid price the whole list is used | Barbican (not band Y), Royal Court (not Standing), The Place (Standard only) |
| `annotation_attrs` | free-text instance attributes → annotations | Kiln (`AccessPerformance`), Young Vic (`Accessibility`, `Accessibility2`, `PerformanceInformation`), Little Angel (`InstanceInfo`) |
| `finish(scraped, event, instance)` | per-performance touch-up after build | RCM (per-performance page, PWYC price), Blackheath ("free" from `Price`), Brixton (show-page price), Barbican (page description/image) |

## Venues on this helper

| Module | Client | Curation |
|---|---|---|
| `polka.py` | `polka` | `Type` = Show → kids; site join |
| `little_angel_theatre.py` | `littleangeltheatre` | `EventType` = In-house show → kids; plan venue Theatre / Studios; site join |
| `soho_theatre.py` | `sohotheatre` | `Venue` room → Dean Street / Walthamstow; `WebsiteFilterCategory1` Theatre → theater, Family → kids |
| `barbican.py` | `barbicancentre` | `PrimaryArtForm` + `EventType` (+ `EventGenre` for non-classical music) minus supp/add-on/members-only and Raymond Gubbay; films only if on barbican.org.uk; plan venue → Barbican / Milton Court / Guildhall / LSO St Luke's |
| `royal_court_theatre.py` | `royalcourt` | listed on royalcourttheatre.com (sitemap, `required`) and `TicketVenue1` = a Jerwood auditorium → theater |
| `young_vic.py` | `youngvic` | not `SupplementaryEvent` and `Venue` room in the four stages → theater |
| `bush_theatre.py` | `bushtheatre` | `WebsiteCategorisation` = Production → theater; site join |
| `donmar_warehouse.py` | `donmarwarehouse` | `Website` = Performance → theater; site join |
| `kiln_theatre.py` | `tricycle` | `Type` Theatre → theater, Cinema → film; site join (two listings) |
| `brixton_house.py` | `ovalhouse` | `Season` = "Season N" and `Genre` New Writing / Youth Theatre → theater, Family Events → kids |
| `arcola_theatre.py` | `arcolatheatre` | `Genre` = Theatre at plan venue "Arcola Theatre"; `Festival` Grimeborn → classical, else theater |
| `park_theatre.py` | `parktheatre` | `Genre` in Drama / Musicals / Comedy / One-off and `Venue` in the three rooms; `RecommendationCategory1` Family → kids, else theater |
| `orange_tree_theatre.py` | `orangetree` | `Type` Classical Play / Drama New Writing at plan venue "Orange Tree Theatre" → theater |
| `camden_peoples_theatre.py` | `camdenpeoplestheatre` | every performance at plan venue "Camden People's Theatre" → theater |
| `the_yard_theatre.py` | `theyard` | `webUrl` is a theyardtheatre.co.uk event page → theater |
| `southwark_playhouse.py` | `southwarkplayhouse` | listed on southwarkplayhouse.co.uk (`required`) → theater; plan venue → Borough / Elephant |
| `theatre503.py` | `theatre503` | plan venue "Theatre503" and plan not "Theatre503 Writers' Programme" → theater |
| `the_place.py` | `theplace` | `WebsiteListing` Performance, `WebsiteVenue` at The Place, `Type` label in four programmes (Family → dance + kids), not TOUCH TOUR → dance |
| `sinfonia_smith_square.py` | `sinfoniasmithsquare` | `Venue` Hall / Crypt; `Type`/`Series` → classical / jazz / classical + kids |
| `st_martin_in_the_fields.py` | `stmartininthefields` | `Category` Music with a `Genre`, `SubCategories` in the concert series → classical (Family → + kids) |
| `cadogan_hall.py` | `cadoganhall` | `Genre1` (+ `Genre2` exclusions) → classical / jazz / folk / film / classical + kids |
| `royal_college_of_music.py` | `royalcollegeofmusic` | `Category` Concert / Opera → classical; plan venue at SW7 2BS |
| `royal_academy_of_music.py` | `royalacademyofmusic` | listed on ram.ac.uk (sitemap, `required`) with a `Venue` → classical; plan venue "Royal Academy of Music" |
| `blackheath_halls.py` | `blackheathhalls` | `Category` words (event, else instance) → classical / jazz / kids / dance / theater, minus exhibition/talks/take part; `Location` (or postcode) → Halls / ORNC Chapel / Laban Theatre |
| `cecil_sharp_house.py` | `efdss` | efdss.org what's-on section Gigs / Dances → folk; plan venue "Cecil Sharp House" |
| `unicorn_theatre.py` | `unicorntheatre` | `EventType` production types → kids; instance `Owner` Public / Press Night and `Location` in the two auditoria |
