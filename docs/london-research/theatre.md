# London — theatre, contemporary dance, kids/family: venue recon

Probed live 2026-10-24 with curl (Cartelita UA) unless noted. "cffi" = `curl_cffi impersonate="chrome"` (needed only for Cloudflare-fronted *websites*; every ticketing API below answered plain curl).

**Headline:** London is unusually easy. **~30 of the candidates sit on Spektrix and its public v3 API is open on every client tested**: per-performance instances, structured genre attributes, and real prices. Seven more (NT, Sadler's Wells, Southbank, Old Vic, Globe, Almeida, Hampstead) are on **Tessitura TNEW v7**, and one undocumented-but-public POST returns every production with all its performances. Three small houses use **Ticketsolve/Lineup**, which has an XML feed. So three shared helpers cover nearly the whole list.

---

## 1. Venue table

Legend: **Spk** = Spektrix v3 (`https://system.spektrix.com/<client>/api/v3/...`), **TNEW** = Tessitura TNEW v7 (`POST https://<host>/api/products/productionseasons`), **TS** = Ticketsolve (`https://<sub>/shows.xml`). "Perf dates" means one row per performance with date and time. Counts are what I saw today: events with an instance on or after today, plus instances.

### Theatre

| Venue | Area | Why it fits | URL | Platform + data source | Per-perf dates? | Genre labels? | Scrapeability | Conf. |
|---|---|---|---|---|---|---|---|---|
| **National Theatre** (Olivier/Lyttelton/Dorfman) | South Bank | The national subsidised house | nationaltheatre.org.uk | **TNEW** `tickets.nationaltheatre.org.uk` (20 productions / 373 perfs). The website's production pages also carry **JSON-LD Event per performance** (70 on Cloud 9) with `location.name` = auditorium, and a price ladder in the HTML ("£25, £36, £51…") | Yes, both sources | None from TNEW (`keywords` null). All theatre. Filter out touring/West End items (Hadestown, West Side Story appear on /whats-on) by JSON-LD location | Easy. The WP site is fine with httpx, with Cloudflare only on assets | High |
| **Young Vic** | Waterloo | Bold directors, local programme | youngvic.org | **Spk `youngvic`** (18 events). The website is a Cloudflare 403 for curl; cffi gets through (200) | Yes | `Genre` = New writing / Revival / Studio / Musical; `SupplementaryEvent`=True marks ancillaries (headsets, programmes, touch tours appear as events, so filter them) | Easy (API needs no website access) | High |
| **Royal Court** | Sloane Sq | New writing, the defining one | royalcourttheatre.com | **Spk `royalcourt`** (25 upcoming / 743 instances) | Yes | None needed (all new writing). `TicketVenue1` = Downstairs/Upstairs/Bar. Drop off-site rows (bowling party, galas) via `TicketVenue2` | Easy | High |
| **Almeida** | Islington | New work/reinventions | almeida.co.uk | **TNEW** `ticketing.almeida.co.uk` (4 productions / 107 perfs). The website shows ranges and prices ("£10 / £8") | Yes (TNEW) | No (all theatre) | Easy | High |
| **Donmar Warehouse** | Covent Garden | Subsidised 250-seater | donmarwarehouse.com | **Spk `donmarwarehouse`** (6 upcoming / 502 inst.) | Yes | `Website` = Performance / Development event, so keep Performance | Easy | High |
| **Bush Theatre** | Shepherd's Bush | New writing, diverse voices | bushtheatre.co.uk | **Spk `bushtheatre`** (12 / 600). Prices confirmed (£10/£15…) | Yes | `WebsiteCategorisation` = Production / Supplementary; `Genre`=New Writing | Easy | High |
| **Arcola** | Dalston | Fringe/international, local | arcolatheatre.com | **Spk `arcolatheatre`** (8 upcoming / 1700). The WP Spektrix plugin and custom domain `boxoffice.arcolatheatre.com` were also seen | Yes | `Genre` = Theatre / Workshop | Easy | High |
| **Battersea Arts Centre** | Battersea | Experimental, live art, family | bac.org.uk | **Spk `bac`** (27 / 424). Cloudflare on the website only | Yes | `Workstream` = Public Programme / Grand Hall (hires/gigs) / Business Development. No artform label: theatre/live art vs kids needs website tags | Easy (data). Category: medium | High |
| **Southwark Playhouse** (Borough + Elephant) | Southwark | Fringe/new musicals | southwarkplayhouse.co.uk | **Spk `southwarkplayhouse`** (11 events). Client name guessed and confirmed via the API | Yes | None (theatre and musicals) | Easy | High |
| **Soho Theatre** (+ Walthamstow) | Soho / Walthamstow | New writing, comedy, cabaret | sohotheatre.com | **Spk `sohotheatre`** (161 events, ~1480 upcoming instances; /instances without `startFrom` times out, so always filter) | Yes | **Excellent**: `WebsiteFilterCategory1` = Comedy / Theatre / Cabaret / Family / Music. `Venue` distinguishes Walthamstow and the Glasgow Glee Club (exclude). Whitelist theatre and family. Comedy belongs to another scope | Easy | High |
| **Hampstead Theatre** | Swiss Cottage | New writing main + Downstairs | hampsteadtheatre.com | **TNEW** `my.hampsteadtheatre.com` (6 / 108). The website production page also lists perfs and prices | Yes | No (theatre). Note Kimberly Akimbo is a musical | Easy | High |
| **Kiln** | Kilburn | Local/political new writing | kilntheatre.com | **Spk `tricycle`** (25 / 466). Cloudflare on the website | Yes | `WebEventType`/`Type` = Theatre / Cinema / Supplementary / Hire. Whitelist Theatre, so cinema is excluded or goes elsewhere | Easy | High |
| **Lyric Hammersmith** | Hammersmith | Young, local, kids strand | lyric.co.uk | **Spk `lyrichammersmith`** (102 / 2373) | Yes | `Type` = Lyric Main House / Children's Show / Christmas Shows / For The Culture / Music / Other; `MarketingCodingPrimary` (Contemporary Play, Comedy & Comedians, Little Lyric…). Many YPBOC youth-programme rows (`Programme`=YPBOC), so exclude them | Medium (noisy) | High |
| **Theatre Royal Stratford East** | Stratford | Community, Black/Asian work | stratfordeast.com | **Spk `stratfordeast`** (7 / 97) | Yes | `WebsiteChannel` = Production / Other event; `AdditionalGenreOrType` (Pantomime) | Easy | High |
| **Shakespeare's Globe** | Bankside | Repertory, Sam Wanamaker | shakespearesglobe.com | **TNEW** `basket.shakespearesglobe.com` (459 KB: includes Exhibition and tours as productions). Queue-it "safetynet" cookie passed with plain curl | Yes | No. Exclude tours/exhibition/CPD by productionSeasonId or website type | Medium (needs filtering) | Med-High |
| **Barbican Theatre** | City | International theatre/dance | barbican.org.uk | **Spk `barbicancentre`** (437 upcoming events). Use `?instanceStart_from=`, because the unfiltered call times out | Yes | `PrimaryArtForm` = Theatre / Classical / Cinema / Contemporary Music / Other… Dance is coded **Theatre** (Boy Blue), so a theatre/dance split needs the website label. Also `Settlement`=Rental | Easy (data), medium (dance split) | High |
| **Orange Tree** | Richmond | Rediscoveries + new writing in the round | orangetreetheatre.co.uk | **Spk `orangetree`** (32 / 447) | Yes | `Type` = Classical Play / Drama New Writing / Chamber & Recitals / Literary Talks | Easy | High |
| **Old Vic** | Waterloo | Big but independent, not West End | oldvictheatre.com | **TNEW** `my.oldvictheatre.com` (POST works. Queue-it on /events) | Yes | No | Easy | Med (borderline curation: star-led) |
| **Jermyn Street Theatre** | St James's | Tiny studio, revivals | jermynstreettheatre.co.uk | **TS** `jermynstreettheatre.ticketsolve.com/shows.xml` (6 shows / 79 perfs) | Yes | `event_category` empty | Easy | High |
| **Finborough** | Earl's Court | Rediscoveries/new writing pub theatre | finboroughtheatre.co.uk | Website returns 429/Cloudflare to curl (cffi OK). It has an **open Payload CMS API** `finborough2024-backend-production.up.railway.app/api/productions` (545 docs: start/end, weekly `times`, `ticket_options` prices, `lineup_id`) | **No**: range plus weekly times only. Booking via Lineup (`lineup_id`); feed host not found | `type` (main / …) | Medium. Would need expansion or the Lineup feed | Med |
| **The Yard** | Hackney Wick | New work, local | theyardtheatre.co.uk | **Spk `theyard`** (8 events). The Next.js site also embeds runs | Yes | None (filter "Name a Seat" etc.) | Easy | High |
| **Camden People's Theatre** | Euston | Fringe/devised/new | cptheatre.co.uk | **Spk `camdenpeoplestheatre`** (27 / 575) | Yes | `FinancialArrangement` (Guarantee / External hire). No artform | Easy | High |
| **Brixton House** (ex-Ovalhouse) | Brixton | Local new writing, live art | brixtonhouse.co.uk | **Spk `ovalhouse`** (20 upcoming / 2313) | Yes | `Genre` = New Writing / Comedy / Family Events / Youth Theatre / Live Art / Talks and Workshops / Community Projects | Easy | High |
| **New Diorama** | Euston | Ensemble/devised companies | newdiorama.com | **TS** `newdiorama-tickets.newdiorama.com/shows.xml` (31 perfs). `event_attribute` PREVIEW, per-event URL, status | Yes | Empty `event_category`; `<tag>`s are season codes | Easy | High |
| **Omnibus** | Clapham | Local arts centre, theatre + jazz | omnibus-clapham.org | **Spk `omnibustheatre`** (12 events). The website is Wix; `purchase.omnibus-clapham.org` is a custom Spektrix front | Yes | No attributes, and jazz is mixed in. Need a website label or a curated whitelist | Easy data, medium category | Med |
| **Park Theatre** | Finsbury Park | New writing | parktheatre.co.uk | **Spk `parktheatre`** (37 / 2152). `webUrl` populated on some | Yes | `Genre` = Drama / Comedy / Musicals / Supplementary event / One-off; `Venue` (Events Elsewhere, so exclude) | Easy | High |
| **Coronet Theatre** | Notting Hill | International theatre/dance/music | thecoronettheatre.com | **Spk `theprintroom`** (11 / 43) | Yes | None | Easy | High |
| **Bridge Theatre** | London Bridge | Big commercial-producing (LT) | bridgetheatre.co.uk | Trafalgar Tickets `booking.bridgetheatre.co.uk` (Next.js, Contentful) | Not checked | — | Hard/unknown | Low (curation borderline) |
| **Hackney Empire** | Hackney | Variety house | hackneyempire.co.uk | **Spk `hackneyempire`** (41 upcoming / 258) | Yes | **None** in the API (only `ExcludeFromTwickets`). Programme is mostly comedy and music, plus panto, Ballet Black, opera. Website listing is JS-rendered | Easy data, hard category | Med |
| Theatre503 | Battersea | New writing | theatre503.com | **Spk `theatre503`** (18; includes online masterclasses, so filter) | Yes | `Writer` only | Easy | High |
| Jacksons Lane | Highgate | Circus/kids/theatre | jacksonslane.org.uk | **Spk `jacksonslane`** (24) | Yes | `Genre` = Jacksons Juniors / Circus / Theatre / Christmas / Guest Event | Easy | High |
| Shoreditch Town Hall | Shoreditch | Site-responsive theatre | shoreditchtownhall.com | **Spk `shoreditchtownhall`** (12) | Yes | None | Easy | Med |
| King's Head Theatre | Islington | Queer/fringe | kingsheadtheatre.com | **Spk `kingsheadtheatre`** (6) | Yes | `Genre` = Pantomime / Drama / Comedy | Easy | Med |
| Greenwich Theatre | Greenwich | Local producing/receiving | greenwichtheatre.org.uk | **Spk `greenwichtheatre`** (33) | Yes | `WebsiteCategory` = Main House / Studio / Family / Workshops; `TypeOfProduction` | Easy | Med (lots of touring tribute) |
| Riverside Studios | Hammersmith | Theatre + cinema arts centre | riversidestudios.co.uk | **Spk `riversidestudios`** (custom `spektrix.riversidestudios.co.uk`; 102) | Yes | `EventType` = Theatre / Cinema / Music / Workshops… | Easy | Med |
| Theatre Peckham | Peckham | Local/young people's theatre | theatrepeckham.co.uk | **TS** `theatrepeckham.ticketsolve.com/shows.xml` (10 shows / 45 perfs) | Yes | `event_category` = Drama / Theatre / Dance / Musical (partly filled) | Easy | Med |
| Tara Theatre | Earlsfield | South Asian theatre | tara-arts.com | **Spk `taraarts`** (6, currently readings) | Yes | `Company` | Easy | Low (thin programme) |
| Chickenshed | Southgate | Inclusive theatre | chickenshed.org.uk | **Spk `chickenshed`** (20, many workshops) | Yes | Only `EventSubvenue` | Easy | Med |
| ~~Gate Theatre~~ | Notting Hill | — | gatetheatre.co.uk | Spk `gate`: no upcoming | — | — | **Closed** (site announces the closure) | — |

### Contemporary dance

| Venue | Area | Why it fits | URL | Platform + data source | Per-perf dates? | Genre labels? | Scrapeability | Conf. |
|---|---|---|---|---|---|---|---|---|
| **Sadler's Wells** (+ Lilian Baylis, Peacock, Sadler's Wells East) | Islington / Holborn / Stratford | London's dance house | sadlerswells.com | **TNEW** `my.sadlerswells.com` (68 productions / 345 perfs). **Website event pages render every performance** in `c-event-instance` blocks: date, time, "From: £30.00", venue name (Sadler's Wells Theatre / Peacock / Lilian Baylis / East), `data-booking-url` = TNEW perf URL. Website plain curl 200 | Yes | All dance. Venue label lets you split Peacock (often commercial) | Easy | High |
| **The Place** | Euston | Contemporary dance home, Resolution festival | theplace.org.uk | **Spk `theplace`** (101 events) | Yes | `WebsiteListing` = Performance / Class / Children and Youth Dance (structural). `Type` = Theatre Programme / Family Programme / Resolution… Keep `Performance` | Easy | High |
| **Southbank Centre** (QEH, Purcell Room) | South Bank | Performance & dance programme | southbankcentre.co.uk | **TNEW** `secure.southbankcentre.co.uk` (POST 200, 285 KB, all artforms). Website: Cloudflare (plain curl 403; cffi 200). Event pages have JSON-LD `TheaterEvent` + `AggregateOffer`, "category: Performance & dance", perf links `secure…/142904/142905` | Yes | Website category ("Performance & dance", Classical…) is structural. Join TNEW perfs to website pages by productionSeasonId in the perf URL | Medium (two sources, cffi) | High |
| **Barbican** (dance) | City | International dance | — | see Barbican above | Yes | Dance is lumped into `PrimaryArtForm=Theatre` | Medium | High |
| **Dance Umbrella** (festival, Oct) | Multi-venue | London's contemporary dance festival | danceumbrella.co.uk | WP `/event/<slug>/` pages with date and price text ("Sat 24 October 2026, 1pm", £8/£15). Tickets sold by host venues (Rich Mix, The Place, Southbank…) | Per event (one-offs) | All dance | Medium. Mostly covered through the host venues' feeds already | Med |
| Rich Mix | Bethnal Green | Hosts dance (DU), music, film | richmix.org.uk | **Spk `richmix`** (8) | Yes | **`PrimaryCategory` = Dance / Performance / Screening**; `WebsiteChannel` LIVE/FILM | Easy | Med |
| Trinity Laban | Deptford | Conservatoire dance/music shows | trinitylaban.ac.uk | Website what's-on JS-rendered, no feed found. Cloudflare | ? | — | Hard/unknown | Low |
| Siobhan Davies Studios | Elephant | Mostly classes, few performances | siobhandavies.com | WP `/events/` + `/events/feed/` | ? | — | Low value (classes) | Low |
| Rambert | — | Touring company, no London venue programme | rambert.org.uk | — | — | — | Exclude (perform at Sadler's etc.) | — |

### Kids / family

| Venue | Area | Why it fits | URL | Platform + data source | Per-perf dates? | Genre labels? | Scrapeability | Conf. |
|---|---|---|---|---|---|---|---|---|
| **Unicorn Theatre** | London Bridge | UK's leading kids' theatre | unicorntheatre.com | **Spk `unicorntheatre`** (10 / 613). Prices confirmed (child £12, combos) | Yes | All kids. `AgeGuide` (4+…), `EventType` Unicorn Production / Co-pro / Visiting | Easy | High |
| **Little Angel Theatre** | Islington | Puppetry for kids | littleangeltheatre.com | **Spk `littleangeltheatre`** (18 / 379) | Yes | **`EventType` = In-house show / Family activity / Adult short course / Children only activity**. Keep shows (and family activity if wanted) | Easy | High |
| **Polka Theatre** | Wimbledon | Kids-only theatre | polkatheatre.com | **Spk `polka`** (47) | Yes | **`Type` = Show / Holiday Workshop / Drop-in Workshop / Ancillary Event / School Workshops / Saturday Club**; `AgeRange` | Easy | High |
| Half Moon | Limehouse | Young people's theatre | halfmoon.org.uk | WP event pages list each perf with price ("Sat 31 Oct 11:00 £9 Book Tickets") | Yes (HTML) | All kids | Easy (HTML) | Med |
| Lyric (Little Lyric), Soho (Family), BAC, Jacksons Lane (Juniors), Greenwich (Family), Stratford East | — | Family strands of mixed houses | — | via their Spk attributes above | Yes | Structural labels exist at Lyric (`Type`=Children's Show), Soho (`WebsiteFilterCategory1`=Family), Jacksons Lane, Greenwich | Easy | High |

---

## 2. Platform analysis

### Spektrix (about 34 clients): one shared helper covers the bulk

Royal Court, Young Vic, Donmar, Bush, Arcola, BAC, Southwark Playhouse, Soho, Kiln (`tricycle`), Lyric (`lyrichammersmith`), Stratford East, Barbican (`barbicancentre`), Orange Tree, The Yard (`theyard`), CPT, Brixton House (`ovalhouse`), Omnibus (`omnibustheatre`), Park, Coronet (`theprintroom`), Hackney Empire, Theatre503, Jacksons Lane, Shoreditch Town Hall, King's Head, Greenwich, Riverside Studios, Chickenshed, Tara (`taraarts`), Rich Mix, The Place (`theplace`), Unicorn, Little Angel (`littleangeltheatre`), Polka (`polka`).

How to find a client name: `client-name="…"` on `<spektrix-*>` web components, or the path segment on the custom domain (`tickets.bushtheatre.co.uk/bushtheatre/…`). For the rest, guessing against `system.spektrix.com/<guess>/api/v3/events` works (404 vs 200).

Endpoints, all open with no auth and verified:
- `GET /api/v3/events?instanceStart_from=YYYY-MM-DD`: upcoming events with `name`, `description`/`htmlDescription`, `imageUrl`, `duration`, `first/lastInstanceDateTime`, and **client-specific `attribute_*` fields**. These are the structural labels for the category whitelist (Soho `WebsiteFilterCategory1`, Kiln `WebEventType`, Polka `Type`, The Place `WebsiteListing`, Little Angel `EventType`, Brixton House `Genre`, Park `Genre`, Rich Mix `PrimaryCategory`, Barbican `PrimaryArtForm`…). The attribute *names* differ per client, so the helper takes a per-venue config: `{attr: allowed values → category}`.
- `GET /api/v3/instances?startFrom=YYYY-MM-DD`: **one row per performance** (`start`, `event.id`, `cancelled`, `isOnSale`, `priceList.id`, instance attributes such as `Location`, `Preview`, `Captioned`, `AudioDescribed`). Without the filter Soho/Barbican time out. Note `instanceStart_from` does **not** work on /instances; it's `startFrom` there.
- `GET /api/v3/instances/{id}/price-list`: real amounts per ticket type and band. Dedupe by `priceList.id` to keep request counts low, then render as free text ("£10–£25").
- `webUrl` is almost always empty, so the event link is either the venue's website page (needs a light website listing scrape or slug match) or the Spektrix booking URL (`https://<custom-domain>/<client>/website/EventDetails.aspx?EventId=<numeric prefix of id>`, still to be verified).
- Gotchas: events include **ancillaries** (programmes, headsets, touch tours, "Name a Seat", staff lunches at the Barbican, online masterclasses, gift items). Filter with the structural attribute (`SupplementaryEvent`, `WebsiteCategorisation`, `Type`) and require ≥1 upcoming instance. A few clients (Royal Court, CPT, Coronet, Southwark, Hackney Empire, Omnibus) have no artform attribute: fine when the house is single-genre, a problem for Hackney Empire and Omnibus.

### Tessitura TNEW v7 (7 venues): second shared helper

NT (`tickets.nationaltheatre.org.uk`), Sadler's Wells (`my.sadlerswells.com`), Southbank (`secure.southbankcentre.co.uk`), Old Vic (`my.oldvictheatre.com`), Globe (`basket.shakespearesglobe.com`), Almeida (`ticketing.almeida.co.uk`), Hampstead (`my.hampsteadtheatre.com`).

- Endpoint (found in TNEW's `tnew-event-listing.*.js`): `POST /api/products/productionseasons` with JSON `{"startDate":"2026-10-24T00:00","endDate":"2027-03-01T00:00"}` and a session cookie from a prior `GET /events`. Old Vic and Globe front /events with Queue-it "safetynet", but a plain-curl cookie jar passed. Returns `productions[]` → `performances[]` with `iso8601DateString`, `displayTime`, `actionUrl` (`…/<prodSeasonId>/<perfId>`), `isOnSale`, `performanceStatusMessage`, `productTypeId`.
- **Missing from TNEW:** price, auditorium, genre, description (`keywords` null everywhere tested). So every TNEW venue pairs the feed with the venue's own website page. NT JSON-LD gives location, Sadler's instance blocks give venue + "From £", Southbank gives JSON-LD `AggregateOffer` + "Performance & dance" category, Hampstead/Almeida give a price list in HTML. The join key is the `<prodSeasonId>/<perfId>` in the website's booking links, which all four sites embed.
- Sadler's and NT websites each already render every performance, so either could be a website-only scraper. TNEW is the fallback/cross-check.

### Ticketsolve / Lineup (3, possibly 4): third, small helper

New Diorama, Jermyn Street, Theatre Peckham (Finborough's CMS carries a `lineup_id`, which points to Lineup, Ticketsolve's successor, but I didn't find its feed host). `GET https://<sub>.ticketsolve.com/shows.xml` (or the custom domain) gives venue → show → event with `date_time_iso`, per-event URL, `status`, `event_attribute` (PREVIEW), `event_category` (often empty). No price in the list feed. Per-event `.xml` may have it (not checked).

### Bespoke

Finborough (Payload CMS JSON, ranges only), Half Moon (WP HTML per-perf), Dance Umbrella (WP), Bridge (Trafalgar Tickets / Next.js, not investigated), Trinity Laban (JS, nothing found).

### Cloudflare

Websites for Young Vic, Southbank, Finborough (429), Kiln/BAC/Barbican/Sadler's/Laban (CF present, but plain curl got 200). **No ticketing API was CF-blocked.** Where the website is needed (Southbank, Young Vic, Finborough), `curl_cffi impersonate="chrome"` returned 200. No headless browser was needed anywhere.

---

## 3. Exclusions

- **Gate Theatre**: closed (announced on its site; Spektrix has no future events).
- **Rambert**: touring company with no venue programme of its own; its London dates appear at Sadler's etc.
- **Siobhan Davies Studios**: almost all classes/hires; revisit only if there's a performance strand.
- **Trinity Laban**: no accessible feed found, and student showcases are low on "worth leaving the house for" for a general audience. Low priority.
- **Bridge Theatre** and arguably **Old Vic**: big star-led producing houses that sit near West End fare. Old Vic is trivially scrapeable via TNEW, so it's a curation call. Bridge is unprobed (Trafalgar platform).
- **Hackney Empire**: mostly stand-up/music/tribute nights, with no structural genre in the API. Could be added later for comedy/music with a website label, or with a small hand-curated whitelist of theatre/dance productions (not title keywords).
- **Tara Theatre**: currently only readings and comedy. Recheck.
- West End commercial houses (ATG/Delfont/Nimax/LW): out of scope by curation.

---

## 4. Recommended starter set

Build the **Spektrix helper first**: one parser, config = `(client, venue_slug, attribute→category map, exclusion attrs)`. Then TNEW and Ticketsolve.

**Wave 1 (Spektrix, clean structural labels, high curation fit):**
1. Royal Court (`royalcourt`): theatre
2. Young Vic (`youngvic`): theatre (`SupplementaryEvent` filter)
3. Bush (`bushtheatre`): theatre (`WebsiteCategorisation=Production`)
4. Donmar (`donmarwarehouse`): theatre (`Website=Performance`)
5. Soho Theatre (`sohotheatre`): theatre + family via `WebsiteFilterCategory1`. Comedy is ready for later
6. Kiln (`tricycle`): theatre via `WebEventType`
7. Brixton House (`ovalhouse`): theatre/live art/family via `Genre`
8. Arcola (`arcolatheatre`), Park (`parktheatre`), Orange Tree (`orangetree`), CPT (`camdenpeoplestheatre`), The Yard (`theyard`), Southwark Playhouse (`southwarkplayhouse`), Theatre503: theatre
9. The Place (`theplace`): **dance** via `WebsiteListing=Performance`
10. Unicorn (`unicorntheatre`), Little Angel (`littleangeltheatre`, `EventType=In-house show`), Polka (`polka`, `Type=Show`): **kids**

**Wave 2 (TNEW helper + website enrichment):**
- Sadler's Wells (dance. The website alone suffices: date, time, price, sub-venue)
- National Theatre (theatre. JSON-LD per perf on the website + TNEW)
- Southbank Centre (dance/performance. TNEW + cffi website for the category)
- Almeida, Hampstead (theatre)
- Globe (theatre, filter tours/exhibition)

**Wave 3:** Ticketsolve helper (New Diorama, Jermyn Street, Theatre Peckham); Barbican theatre/dance (needs the website label to split dance from theatre); Lyric Hammersmith (noisy attributes but good kids strand); BAC; Stratford East; Coronet; Rich Mix (dance); Half Moon (HTML); Finborough (CMS ranges, or find the Lineup feed).

That gives about 25 strong venues across theatre/dance/kids from **three parsers**, with structural category labels at almost every mixed house and real per-performance rows everywhere except Finborough.
