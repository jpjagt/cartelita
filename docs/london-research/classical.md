# London: classical, opera, early/contemporary and folk. Venue research

Probed live on 2026-10-24 with curl (Cartelita UA). Where a site blocked curl I tried `curl_cffi impersonate="chrome"`. Probes were kept light, and nothing was written to the repo.

**Headline:** most of London's classical sector runs on **Spektrix**, and its public v3 API (`https://<domain>/<client>/api/v3/events`, `/instances`, `/instances/{id}/price-list`) answered **200 with JSON and no auth for 13 of 13 clients tested**. Several clients also expose their own structural genre attributes (`attribute_Genre`, `attribute_EventType`, `attribute_SubCategories`…). One shared `SpektrixScraper` helper could cover about 10 starter venues.

## 1. Candidates

| Venue | Area | Why it fits | URL | Data source + platform | Genre discriminator? | Scrapeability | Confidence |
|---|---|---|---|---|---|---|---|
| **Wigmore Hall** | Marylebone | World's chamber/song hall. Cheap Under-35 tickets, BBC Lunchtime (Mon 1pm), Sunday Morning coffee concerts. Huge local regular base | wigmore-hall.org.uk/whats-on | **JSON** `GET /api/v1/listings/whats-on?page=N` (its own Next.js app, Tessitura behind it): 296 items in 25 pages, with `date`, `url`, `title`, `subtitleText`, **`pricesText` ("£50 £43 £33 £27 £18")**, image. Event pages carry `genres` (Song, Contemporary…) | Not needed: the whole venue is classical. Optional genres per event page; series pages (lunchtime, Sunday morning) | **easy** | high |
| **Southbank Centre** (RFH, QEH, Purcell Room) | South Bank | Resident orchestras (LPO, Philharmonia, OAE, London Sinfonietta), plus free foyer music | southbankcentre.co.uk/whats-on/?artform-filter=classical-music | WordPress (Substrakt). Server HTML listing, 12 per page, `/whats-on/page/N/?artform-filter=classical-music`. Card shows a **`c-event-card__primary-artform` pill** ("Classical music"), date or date range, room. Detail page has **JSON-LD `MusicEvent`** and "Tickets from £20". `wp-json` returns 403 | **Yes**: `artform-filter` slugs (classical-music, gigs, performance-dance…) and the primary-artform pill. These are the source's own labels | **medium**: listing is fine with curl, but detail pages sometimes get a Cloudflare challenge with curl (403 "Just a moment"). `curl_cffi` passes | high |
| **Barbican** (Hall, plus Milton Court/LSO St Luke's rentals) | City | LSO and BBC SO home, Barbican Presents, contemporary | barbican.org.uk/whats-on/classical-music | **Spektrix** `spektrix.barbican.org.uk/barbicancentre/api/v3`. ⚠ An unfiltered `/events` **hangs (more than 60s)**, so always pass `?instanceStart_from=…&instanceStart_to=…` (3 months gave 287 events in 1.7s). Its website HTML (200) also has a classical listing | **Yes, rich**: `attribute_PrimaryArtForm` (Classical Music / Contemporary Music / Cinema / Theatre…), `attribute_EventType` (Orchestral / Chamber / Recital / Choral / Opera and Oratorio / Concert / Screening…), `attribute_EventGenre` (e.g. "The Baroque era", "Contemporary Classical", Jazz, South Asian Music) | **easy** with Spektrix (`webUrl` is empty, so the event URL must come from the website) | high |
| **LSO St Luke's** | Old Street | LSO's own hall. **Free Friday Lunchtime Concerts**, BBC R3 lunchtimes, chamber, Gresham lectures | lso.co.uk/whats-on/?location=lso-st-lukes | Server HTML (Netlify behind Cloudflare, curl 200). Cards with date/time text, `/whats-on/page/N/?location=lso-st-lukes`. Ticketing is a custom SPA at `tickets.lso.co.uk`, not Spektrix | Location filter. `?category=` (family-events, on-tour). Essentially a single-category venue (classical) | **easy/medium** (HTML paging, price on detail page) | high |
| **Milton Court / Guildhall School** | City | Conservatoire. Many free/cheap student concerts and opera | gsmd.ac.uk/whats-on | Drupal; the listing is JS-loaded (facets event_category/event_type; endpoint not found in a quick look). Public Milton Court concerts are also in **Barbican Spektrix** (`attribute_GSMDEvent=True`, venue "Guildhall School") | Drupal facet `event_category`, but not reachable | **medium/hard** directly; **easy via the Barbican feed** for the public subset | medium |
| **Kings Place** | King's Cross | Independent hall. Classical, **folk**, jazz and contemporary series, with a loyal local crowd | kingsplace.co.uk/whats-on/ | **Spektrix** `ticketing.purchase.kingsplace.co.uk/kingsplace/api/v3` (200, 291 events), but with **no genre attributes**. The website returns **403 Cloudflare to curl; curl_cffi gets 200**. Its URLs put genre in the path: `/whats-on/classical/…`, `/whats-on/folk/…`, `/whats-on/jazz/…`, plus `data-genre` ids | **Yes, on the website** (URL path segment). Hybrid: genre pages from the site via curl_cffi, joined to Spektrix for dates and prices | **medium** | high |
| **St John's Smith Square** (now "Sinfonia Smith Square") | Westminster | Baroque festival, **Lunchtime Concerts**, choral, Jazz in the Crypt | sinfoniasmithsq.org.uk/whats-on | **Spektrix** `checkout.sinfoniasmithsq.org.uk/sinfoniasmithsquare/api/v3` (96 events) | **Yes**: `attribute_Type` (Orchestral / Choral / Chamber / Organ / Vocal / Opera / Jazz…), `attribute_Series` (Lunchtime Concerts, London Festival of Baroque Music, Jazz in the Crypt) | **easy** | high |
| **St Martin-in-the-Fields** | Trafalgar Sq | Free/donation **lunchtime concerts**, Masterworks series, choral, Crypt jazz. ⚠ Also runs a big house-produced **"Candlelight Concerts"** tourist series | stmartin-in-the-fields.org/whats-on | **Spektrix** `tickets.stmartin-in-the-fields.org/stmartininthefields/api/v3` (265 events) | **Yes, and it solves the candlelight problem structurally**: `attribute_SubCategories` = Candlelight Concerts (98) / Masterworks (58) / Lunchtime Concerts (15) / Choral Discovery Concerts / Crypt Live / Lectures… Whitelist Masterworks, Lunchtime, Choral Discovery and Crypt Live (to the jazz list, if wanted). Also has `attribute_Genre` and `attribute_Category` | **easy** | high |
| **Cadogan Hall** | Sloane Sq | RPO home, choral, early music. ⚠ Also a rental hall (tribute acts, pop, comedy) | cadoganhall.com/whats-on | **Spektrix** `tickets.cadoganhall.com/cadoganhall/api/v3` (205 events). `webUrl` is filled for 141 of them | **Yes**: `attribute_Genre1` (Orchestra, Choral, Opera, Folk, Jazz, Pop, Rock / Country, Talk…), `attribute_Genre2` (Early Music, Contemporary Classical, Recital / Chamber, Tribute, Christmas…), `attribute_WebsiteCategory` | **easy** | high |
| **Royal Ballet & Opera (ROH)** | Covent Garden | The opera house. Also Linbury Theatre, free lunchtime/insight events | rbo.org.uk/tickets-and-events | Craft/React. **`window.__REACT_QUERY_DEHYDRATED_STATE__` JSON in server HTML**: 103 events, each with `performances[] {date, performanceType}`, `locations`, `tags`. Pages `?page=N`. Price not in the listing (production page) | **Yes**: tag ids, with names in the same JSON: "Opera and music" (921) vs "Ballet and dance" (922), "Cinema broadcasts", "Talks and insights", "Tours", "Rehearsals" | **easy** | high |
| **ENO (London Coliseum)** | Covent Garden | English-language opera at popular prices, with young-audience free tickets | eno.org/whats-on | **Spektrix** `tickets.booking.eno.org/londoncoliseumlimited/api/v3` (137 events), but the client is the *Coliseum*: ballet galas, musicals, bars, VIP and "Dress Rehearsal" items all mixed in. `attribute_ENOEvent` is unreliable (0 current productions flagged) | **Partial**: no clean genre attribute. Use **eno.org `/events/…`** (WordPress, about 40 production links; only ENO's own productions) as the whitelist, joined to Spektrix for instances and prices | **medium** | medium |
| **Royal Academy of Music** | Marylebone | Conservatoire. **Lots of free lunchtime/student concerts**, opera scenes | ram.ac.uk/whats-on | **Spektrix** `ticketing.ram.ac.uk/royalacademyofmusic/api/v3` (421 events) | Only `attribute_Venue` (Duke's Hall, Angela Burgess Recital Hall, Susie Sainsbury Theatre…). It's an all-music venue, so a single category works. Price from `/instances/{id}/price-list` | **easy** | high |
| **Royal College of Music** | South Kensington | Conservatoire. Free/PWYC concerts (Chamber Tuesdays, Rush Hour, Elevenses), opera | rcm.ac.uk/events | **Spektrix** `tickets.rcm.ac.uk/royalcollegeofmusic/api/v3` (120 events) | **Yes**: `attribute_Category` (Concert / Opera / Masterclass/Workshop / Museum / Tour / Junior Department…), `attribute_Genre` (Chamber / Orchestral / Opera), `attribute_Faculty`. Whitelist Concert and Opera (and maybe Masterclass) | **easy** | high |
| **Blackheath Halls** (and Trinity Laban) | Blackheath/Greenwich (SE) | Community concert hall in the south-east. Community opera, **many free Trinity Laban student concerts** (Old Royal Naval College chapel, St Alfege) | blackheathhalls.com/whats-on | **Spektrix** `events.blackheathhalls.com/blackheathhalls/api/v3` (490 events; the client covers Blackheath Halls **and Trinity Laban**). The website itself shows a Cloudflare challenge marker | `attribute_Type`/`attribute_Category` are free-text and messy (51 variants: "Music", "music", "Exhibition, music"). Usable structure: `attribute_OrganisationOrVenue` (Blackheath Halls / Trinity Laban / Trinity Music / Laban Theatre), `attribute_Location`, `attribute_EventPostcode`. **`attribute_Price` is a free-text price ("Free", "£10", "Free, Booking Required")**, which fits Cartelera exactly | **easy** to fetch, **medium** to curate (split per venue via Location; Laban Theatre is dance) | high |
| **Conway Hall Sunday Concerts** | Holborn | Longest-running chamber series in Europe (since 1887). Cheap (£14), loyal regulars | conwayhall.org.uk/sunday-concerts | **Ticketsolve** public XML feed `conwayhall.ticketsolve.com/shows.xml` (22 shows), plus a per-event `…/events/<id>.xml` with **prices** (£20 supporter / £14 / £9) and capacity | **Yes**: `<event_category>` = "Sunday Concerts" (vs Talks & Debates, Music, Film…); `<tag>sundayconcerts` | **easy** | high |
| **St James's Piccadilly** | Piccadilly | **Free lunchtime recitals** (Mon/Wed/Fri 1.10pm, donation), The Sixteen residency. ⚠ Also hosts the tourist "Vivaldi Four Seasons by Candlelight" (Piccadilly Sinfonietta) | sjp.org.uk/whats-on/?_filter=music | WordPress. **`/wp-json/wp/v2/event`** is open, with the `event-category` taxonomy. Date/time and "Free admission" live in the page body (ACF is empty in REST), so the detail HTML has to be parsed | **Yes, structural**: `event-category` **`free-concerts`** (272) vs `music` (779, includes candlelight) / `the-sixteen` / `services`… Whitelist free-concerts and the-sixteen, which drops candlelight without title keywords | **medium** | high |
| **St Paul's Cathedral** | City | Free Sunday organ recitals, choral evensong | stpauls.co.uk/search-our-events | Drupal. Search page embeds an event JSON blob (organ recitals visible: "Organ Recital by George Inscoe"), mixed with services and tours | Probably a Drupal event-type taxonomy (not confirmed) | **medium** | medium |
| **Westminster Abbey** | Westminster | Summer organ recital series, Organ Masterpieces | westminster-abbey.org/events | Server HTML (200). Has an organ-recitals section; seasonal | Section pages | **medium** | low (seasonal) |
| **Temple Church** | Temple | Lunchtime organ recitals, Temple Music concerts | templechurch.com/events/concerts-and-recitals | ConcreteCMS calendar (`/ccm/calendar/view_event/...`); concerts are also on templemusic.org | Calendar category URL (concerts-and-recitals) | **medium** | medium |
| **St John's Waterloo** | Waterloo | Community church with a busy concert programme | stjohnswaterloo.org/whats-on | **The Events Calendar REST** `/wp-json/tribe/events/v1/events` open (1188 events, with `start_date`, `cost`, `categories`) | **Yes**: tribe category "Concerts and Live Music" (vs Services…) | **easy** | medium (programme quality not checked) |
| **Handel Hendrix House** | Mayfair | Handel's Salon: baroque in Handel's own rooms | handelhendrix.org/events | Craft CMS, server HTML. Detail shows "Tue 27th Oct 2026 18:30 £25". Small volume. Ticketing is a custom PHP shop | None (mixes Hendrix events). Small and curatable by hand | **easy** (few events) | medium |
| **Opera Holland Park** | Kensington | Summer opera season in the park (Jun–Aug) | operahollandpark.com | **Spektrix** `system.spektrix.com/operahollandpark/api/v3` (24 events) | `attribute_Type` is mostly empty (one "Picnic"). All opera, so a single category | **easy** | high (seasonal) |
| **Cecil Sharp House (EFDSS)** | Camden | HQ of English folk: gigs, ceilidhs, Black British Folk Takeover, choir. Exactly the regulars' scene | efdss.org/whats-on | **Spektrix** `sales.efdss.org/efdss/api/v3` (103 events; also has a few Eventbrite links) | **Yes**: `attribute_TAAArtform` = Music (47) / Dance (30, ceilidhs and balfolk) / Workshops / Literature. Folk list = Music and Dance | **easy** (`webUrl` empty; `attribute_CMSID` links to the efdss.org page) | high |
| **Green Note** | Camden | Small folk/roots/americana venue. Award-winning grassroots venue, nightly shows | greennote.co.uk/events-page/ | WordPress, server HTML listing with title, date, **room** (Green Note / Basement Bar / external Water Rats), **price "£15.00"**. WeGotTickets links | Not needed: folk/roots single category. Promoter prefix in titles ("Folk and Roots Presents") | **easy** | high |
| **Union Chapel** | Islington | Gig venue in a working church. Organ recitals ("Union Chapel presents"), Daylight Music | unionchapel.org.uk/whats-on | Server HTML. Cards have `cat-*`/`cla-*` classes (cla-2=Concert, cla-1=Theatre, cla-3=Workshop; cat-pop/cat-rock), but nearly everything is just `cat-4 cla-2`. Ticketing via DICE / Gigantic | **No useful genre label** (mostly gigs). Belongs in the gigs/indie scope | medium | medium |
| **Walthamstow Folk Club** | Walthamstow | Sunday folk club with established acts (Nancy Kerr & James Fagan…) | walthamstowfolk.co.uk | WordPress homepage posts with date and "Admission £15 (£12 concessions)" in prose | Single category | medium (prose parsing) | medium |
| **Cellar Upstairs Folk Club** | Angel | Monday 8pm traditional folk club, since the 1960s, cash on the door £8/£10 | cellarupstairs.org.uk | WordPress. Programme as one prose list ("7 Sept: San Halen: …"). Price is club-wide | Single category | medium (prose list; year inferred from the "September to December 2026" header) | medium |
| **Islington Folk Club** | Highbury | Thursday folk club ("fiercely traditional to frankly eccentric") | islingtonfolkclub.co.uk/programme.html | Static HTML table: date, venue, artist, note | Single category | **easy** | medium |
| **The Nest Collective** | various (Grand Junction, Cody Dock) | Folk/world promoter: Campfire Club, ceilidhs | thenestcollective.co.uk | Squarespace (has JSON via `?format=json` on collections, not tested) | Single category; multi-venue promoter | medium | low |
| **Arcola (Grimeborn)** | Dalston | Grimeborn opera festival (Aug) | arcolatheatre.com | **Spektrix** `boxoffice.arcolatheatre.com/arcolatheatre/api/v3` (130 events) | **Yes**: `attribute_Festival` = "Grimeborn" (opera), `attribute_Genre` (Theatre…) | **easy** | medium (seasonal) |
| King's Head Theatre | Islington | Was the London pub-opera venue; current programme is drama/comedy/cabaret | kingsheadtheatre.com | Spektrix `tickets.kingsheadtheatre.com/kingsheadtheatre/api/v3` (34 events) | `attribute_Genre`: Drama, Comedy, Musical, Cabaret. **No opera now** | easy | n/a: not in scope |
| Royal Albert Hall | Kensington | Proms (summer), big mixed house | royalalberthall.com | **Blocked**: Imperva "Pardon Our Interruption" for both curl and curl_cffi | unknown | **blocked** (browser only) | n/a |

### Aggregators

| Aggregator | Result |
|---|---|
| **Bachtrack** (London) | Listing body is JS-rendered. curl and curl_cffi both get a 15 KB shell with no events. robots.txt allows `*`. Would need a headless browser or reverse-engineering. **Not worth it**: its London coverage is the same big ticketed houses we can get directly. **hard** |
| **Concert Diary** | ASP.NET. City/region URLs fall back to the homepage (50 UK-wide concerts); has a Cloudflare marker. Mostly amateur choirs UK-wide. **Low value, medium-hard** |
| classical-music.uk | Redirects to gramophone.co.uk, which returns 403 Cloudflare. Not a listings source |

## 2. Platform analysis

### Spektrix: the structural win

The API is public, unauthenticated and needs no special headers: plain httpx with our UA returned JSON for **every client tested** (13 of 13). Endpoints, verified on Sinfonia Smith Square:

- `GET {base}/events`: list of events. Fields: `id`, `name`, `description`/`htmlDescription`, `imageUrl`, `thumbnailUrl`, `duration`, `firstInstanceDateTime`, `lastInstanceDateTime`, `instanceDates` (text), `isOnSale`, `webUrl` (usually empty), plus **client-defined `attribute_*` fields**, which are the per-venue genre labels.
  - Accepts `?instanceStart_from=YYYY-MM-DD&instanceStart_to=YYYY-MM-DD`. **Barbican requires this**: unfiltered, it hangs for more than 60s.
- `GET {base}/instances?startFrom=…&startTo=…`: one row per occurrence (our "one row per occurrence" model). Fields: `id`, `event.id`, `start`, `startUtc`, `cancelled`, `isOnSale`, `priceList.id`, `planId`, plus instance attributes (e.g. `attribute_DoorsOpenAt`).
- `GET {base}/instances/{id}/price-list`: `prices[] {amount, ticketType.name, priceBand.name}`. From this, build the free-text price ("£25–£45", "Free"). `/price-lists/{id}` returned 404. That's one extra call per instance, so cache by `priceList.id`.
- `GET {base}/instances/{id}/status`: availability (optional).
- `GET {base}/venues`: venue names (Barbican's includes "Guildhall School").

| Venue | Spektrix base | Genre attribute(s) worth whitelisting |
|---|---|---|
| Barbican | `https://spektrix.barbican.org.uk/barbicancentre/api/v3` (date filter required) | `PrimaryArtForm`, `EventType`, `EventGenre`; `GSMDEvent` |
| Sinfonia Smith Square | `https://checkout.sinfoniasmithsq.org.uk/sinfoniasmithsquare/api/v3` | `Type`, `Series` |
| St Martin-in-the-Fields | `https://tickets.stmartin-in-the-fields.org/stmartininthefields/api/v3` | `SubCategories` (exclude Candlelight Concerts), `Genre`, `Category` |
| Cadogan Hall | `https://tickets.cadoganhall.com/cadoganhall/api/v3` | `Genre1`, `Genre2`, `WebsiteCategory` |
| Royal College of Music | `https://tickets.rcm.ac.uk/royalcollegeofmusic/api/v3` | `Category`, `Genre` |
| Royal Academy of Music | `https://ticketing.ram.ac.uk/royalacademyofmusic/api/v3` | (`Venue` only; all music) |
| Blackheath Halls / Trinity Laban | `https://events.blackheathhalls.com/blackheathhalls/api/v3` | `OrganisationOrVenue`, `Location`; **`Price` (free text)** |
| EFDSS / Cecil Sharp House | `https://sales.efdss.org/efdss/api/v3` | `TAAArtform` (Music / Dance) |
| Kings Place | `https://ticketing.purchase.kingsplace.co.uk/kingsplace/api/v3` | none; genre comes from the website URL path |
| ENO / Coliseum | `https://tickets.booking.eno.org/londoncoliseumlimited/api/v3` | none reliable; whitelist from eno.org |
| Opera Holland Park | `https://system.spektrix.com/operahollandpark/api/v3` | (all opera) |
| Arcola (Grimeborn) | `https://boxoffice.arcolatheatre.com/arcolatheatre/api/v3` | `Festival` = Grimeborn |
| King's Head Theatre | `https://tickets.kingsheadtheatre.com/kingsheadtheatre/api/v3` | (theatre; out of scope) |

**How to find a client's base:** look on the venue page for `client-name="…"` plus `custom-domain="…"` on `<spektrix-*>` web components, or a `spektrix_api_url` JS variable, or `…/<client>/website/…` iframe links. `system.spektrix.com/<client>/api/v3` also works when there's no custom domain.

**Helper design notes:**
- Use `SourceDefinition` per venue, with config `{base, attribute→category map, attribute whitelist}`, so the category comes from the client's own attributes, never from title keywords.
- **Event URL:** `webUrl` is empty for most clients (Cadogan is 141/205, ENO partial, RAM 8/421). Options: (a) the venue site's own listing, matched on name or Spektrix id (Kings Place, Barbican and ENO pages embed Spektrix ids or booking links); (b) a fallback to the Spektrix booking page `https://<domain>/<client>/website/EventDetails.aspx?EventId=<webEventId or id>` (shape to verify per client). Per-event `source_url` matters for dedup tier 2, but `external_id` = the Spektrix instance id is stable and enough.
- **Date window:** always send `instanceStart_from/to` (or `startFrom/startTo` on `/instances`), for example today to +6 months.
- **Rate:** about 1 call for events, 1 for instances, and N price-list calls (cache by priceList id). Fine for a nightly run.
- **Past events:** some clients return old events (Blackheath starts in 2025; EFDSS "Balfolk 2023"), so filter on instance date.
- Not exposed: `language`. Recurrence is handled by instances.

### Tessitura

Only **Wigmore Hall** among these runs Tessitura (`tessituraId` in its data), and it puts its own JSON API in front: `/api/v1/listings/whats-on?page=N`. No public TNEW endpoint was needed or found, so there's no shared Tessitura helper to build here. ROH, Southbank and LSO use their own stacks.

### Ticketsolve

**Conway Hall** has a public XML feed, `https://<client>.ticketsolve.com/shows.xml`, with `event_category`, tags and per-event XML carrying **prices**. It's generic across Ticketsolve clients (many UK/Irish venues), so a small helper is worth noting for other cities and scopes.

### WordPress REST

St James's Piccadilly (`/wp-json/wp/v2/event` with the `event-category` taxonomy) and St John's Waterloo (The Events Calendar `/wp-json/tribe/events/v1/events`) are both open. Southbank's `wp-json` is blocked (403).

## 3. Exclusions

- **Fever "Candlelight" and lookalikes.** St Martin-in-the-Fields' own "Candlelight Concerts" series (98 events: Four Seasons, carols by candlelight, aimed at tourists) is excluded via `attribute_SubCategories`, while the rest of SMitF stays. St James's Piccadilly's "Vivaldi Four Seasons by Candlelight" (Piccadilly Sinfonietta, "200 performances annually") is excluded by whitelisting only the `free-concerts` and `the-sixteen` categories. Other Fever/Candlelight venues should not be added.
- **Raymond Gubbay / "Classical Spectacular" / tribute nights at rental halls** (Barbican `SeasonPromoter=Raymond Gubbay`, Cadogan `Genre2=Tribute`): exclude through the attribute whitelist.
- **ENO/Coliseum ancillary items** (bars, VIP packages, dress rehearsals, supporter events, Grange Park Opera hospitality): excluded because ENO is whitelisted from eno.org.
- **Royal Albert Hall:** Imperva bot wall. Mixed programme; Proms only in summer. Skip, or revisit with the browser helper.
- **Bachtrack and Concert Diary:** JS-rendered or low value; the venues are covered directly.
- **King's Head Theatre:** no longer an opera venue.
- **Union Chapel:** mainly gigs with no genre label. Better handled in the gigs scope; its organ series could be added later.
- **Irish sessions** (pub sessions, London Irish Centre): no structured listings (Facebook or word of mouth; London Irish Centre `/whats-on/` returned 404). Defer.
- **Grange Park Opera:** outside London (Surrey).

## 4. Recommended starter set

Phase 1 is one `SpektrixScraper` helper plus config. It gives broad coverage cheaply, and every venue has structural labels:

1. **Barbican**: classical via `PrimaryArtForm=Classical Music` / `EventType`. Also picks up Guildhall at Milton Court through `GSMDEvent`.
2. **Sinfonia Smith Square (St John's Smith Square)**: `Type`/`Series`.
3. **St Martin-in-the-Fields**: everything except `SubCategories=Candlelight Concerts`.
4. **Cadogan Hall**: `Genre1` in {Orchestra, Choral, Opera, Classical crossover?} goes to classical, Folk goes to folk, and Tribute is excluded.
5. **Royal College of Music**: `Category` in {Concert, Opera}. Free/PWYC.
6. **Royal Academy of Music**: all events.
7. **Blackheath Halls + Trinity Laban**: music events. Splitting into venues via `Location` needs a multi-venue source (Blackheath Halls, ORNC Chapel, St Alfege), and `Price` is free text already.
8. **Cecil Sharp House (EFDSS)**: `TAAArtform` Music goes to folk, Dance to folk/ceilidh.

Phase 2 is direct sources, each cheap:

9. **Wigmore Hall**: JSON listings API with price text. Top priority for identity: probably the single best venue on the list.
10. **Royal Ballet & Opera**: embedded JSON; the "Opera and music" tag goes to opera, and ballet is routed to dance or left out.
11. **Conway Hall Sunday Concerts**: Ticketsolve XML, `event_category=Sunday Concerts`.
12. **Southbank Centre**: `artform-filter=classical-music` HTML plus JSON-LD on detail pages (curl_cffi).
13. **LSO St Luke's**: HTML, location filter (Free Friday Lunchtimes).
14. **Kings Place**: Spektrix joined to website genre paths (classical, folk) via curl_cffi.
15. **St James's Piccadilly**: WP REST `event-category=free-concerts`. Free lunchtime recitals are exactly what the solo go-er wants.
16. **Green Note**: folk/roots, HTML with prices.

Phase 3 is folk clubs and seasonal: Islington Folk Club (static table, easy), Walthamstow and Cellar Upstairs (prose), ENO (eno.org whitelist joined to Spektrix), Opera Holland Park and Grimeborn (summer, Spektrix), St Paul's, Temple and Westminster Abbey organ recitals, St John's Waterloo (tribe REST).
