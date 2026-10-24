# London: club and grassroots gig venues, Cartelita recon (2026-10-24)

I probed everything live with the Cartelita UA (curl and urllib). The probes were light: one or two requests per venue, plus 7 pages of RA GraphQL and about 100 small DICE calls.

**Headline:** two platform sources cover almost the whole list, so London needs very few per-venue scrapers.

- **DICE** (`partners-endpoint.dice.fm/api/v2/events`, filtered by exact venue name). It sells for about 40 of the venues below and returns structured JSON with **genre_tags, ticket prices, lineup/doors times and status**.
- **Resident Advisor GraphQL** (`ra.co/graphql`). It answers plain httpx with 200, even though RA's HTML pages return a Cloudflare 403. Use it for the club venues not on DICE (Venue MOT, The Cause, Rye Wax…) and as a cross-check.

---

## 1. Venue table

Legend. **Scrapeability:** easy = structured JSON over plain HTTP; medium = HTML parse or ambiguous mapping; hard = JS-only or browser; blocked = no reachable data. **DICE n** = upcoming events returned by the DICE partner endpoint today (100+ means the page was full).

### Club / electronic

| Venue | Area | Category | Why it fits | URL | Data source + platform | Scrape | Conf. |
|---|---|---|---|---|---|---|---|
| fabric | Farringdon (EC1) | club | Long-running, internationally defining club with a resident culture. Big, but independent, and London's reference club | fabriclondon.com | Own site is a JS shell. **DICE "fabric" (13)**, but most of its nights are on **RA venue 237** (5/week). Use RA as the primary source | easy (RA) | high |
| Phonox | Brixton | club | Residency-led single room, strong local scene | phonox.co.uk (WP + JSON-LD) | **DICE "Phonox" (37)**, genres dj:house/techno/dnb. RA 106730 | easy | high |
| FOLD | Canning Town | club | 24h-licence warehouse, queer/techno community, real regulars | fold.london (Squarespace) | **DICE "FOLD" (9)**, RA 155399 (4/wk). DICE alone looks thin, so merge or prefer RA | easy | high |
| Colour Factory | Hackney Wick | club + alternative | Independent Wick space mixing club nights and live gigs (synthpop/indie) | own domain dead (colourfactory.london has no DNS) | **DICE "Colour Factory" (25)**, RA 185559 | easy | high |
| Ormside Projects | Peckham/Bermondsey (SE15) | club / alternative | Small, adventurous, artist-run feel (Nkisi, Night Slugs). No website | — | **RA 108196** (4/wk). DICE "ORMSIDE projects" (5): the API returns the venue name in that casing | easy (RA) | high |
| Venue MOT | South Bermondsey | club / alternative | DIY railway-arch space (breakcore, experimental club). Grassroots to the core | no website (venuemot.com/.co.uk have no DNS) | **RA "M.O.T" 156290** only (6/wk); not on DICE | easy (RA) | high |
| The Cause | Tottenham Hale | club | Volunteer-run community club, still active in 2026 (4 RA events this week) | — | **RA 198121**; not on DICE | easy (RA) | med |
| E1 | Wapping | club | Big techno/hard-techno warehouse, the busiest RA venue (13/wk). Leans party-brand. Optional | e1ldn.com (DNS dead) | **DICE "E1 " (27; note the trailing space)**, RA 141756 | easy | med |
| Village Underground | Shoreditch | club + pop | Arches venue with an independent cultural programme, gigs plus club | villageunderground.co.uk (WP, JSON-LD) | **DICE "Village Underground" (63**, 4 of them tagged "Various Venues, East London", so filter by `venue`) | easy | high |
| EartH | Dalston | pop / alternative / folk / club | Independent Hackney arts centre with a very mixed programme | earthackney.co.uk (WP, JSON-LD) | **DICE "EartH" (77)**, genres indie/electronic/folk/experimental | easy | high |
| XOYO | Old Street | club | Famous residency format, but now partly generic tech-house. Borderline | xoyo.co.uk (JS, Skiddle) | **DICE "XOYO London" (14)** plus Skiddle (key needed). RA 33592 | easy | med |
| Rye Wax | Peckham | club / alternative | Record shop and basement bar, very local | ryewax.com (Wix, 1.5 MB) | Not on DICE and not in this week's RA listings. Wix HTML has JSON-LD and RA links; needs a closer look | medium | low |
| Ridley Road Market Bar | Dalston | club (party) | Tiny, local, much-loved dance bar | ridleyroadmarketbar.com (Wix) | **DICE (50)**, mostly party:pop/disco/ukg. RA 59520 | easy | med |
| Brixton Jamm | Brixton | club | Long-standing Brixton bass/dnb venue | — | **DICE (14)**, RA 1557 | easy | med |
| The Jazz Cafe | Camden | club/soul (likely the jazz list) | Out of scope for this brief, but **DICE 100+** with gig:soul/jazz, dj:house. Worth noting for a London jazz list | — | DICE | easy | high |
| Corsica Studios | Elephant & Castle | club | **Closed** for refurbishment/soundproofing (see §3) | corsicastudios.com returns 503 | — | blocked | high |
| Spiritland | King's Cross | — | Listening bar/restaurant with no ticketed listings found (not on DICE or RA this week). Skip | spiritland.com | — | — | low |

### Grassroots gigs (indie / pop / rock / punk / global)

| Venue | Area | Category | Why it fits | URL | Data source + platform | Scrape | Conf. |
|---|---|---|---|---|---|---|---|
| MOTH Club | Hackney | pop / alternative (also comedy) | Ex-servicemen's club turned the archetypal grassroots venue. Fighting off development (one application refused in March 2026, a second still pending) | mothclub.co.uk (Cargo, DICE widget) | **DICE "MOTH Club" (100+)**, genres indie/alternative; comedy tagged `comedy:*`, so it can be filtered | easy | high |
| The Lexington | King's Cross | pop / rock | Upstairs indie/Americana room, regulars | thelexington.co.uk (video splash page) | **DICE "The Lexington" (60)**: indie/rock/punk/singer-songwriter | easy | high |
| Oslo Hackney | Hackney Central | pop / club | Indie gigs plus late club | site redirects to linktr.ee | **DICE "Oslo Hackney" (56)** | easy | high |
| Windmill Brixton | Brixton | rock / alternative / pop | *The* post-punk incubator (black midi, Squid…) | windmillbrixton.co.uk (HTML calendar, JSON-LD, £ visible) | **DICE "Windmill Brixton" (17)**. Many door-only shows are on its **own site**, so scrape the site (HTML, £ in markup) and use DICE only as a supplement | medium | high |
| The Shacklewell Arms | Dalston | pop / alternative | Indie/psych pub venue | shacklewellarms.com (Squarespace) | **DICE "The Shacklewell Arms" (75)** (the name without "The" returns 0) | easy | high |
| The Victoria | Dalston | pop / alternative | Small pub stage with indie nights | domain dead | **DICE "The Victoria" (53)**: gig:indie plus many party:* nights. The name is generic, so verify the address | easy | med |
| Paper Dress Vintage | Hackney | pop / alternative | Vintage shop with an upstairs gig room | paperdressvintage.co.uk (WP, DICE) | **DICE (47)** | easy | high |
| New River Studios | Manor House | alternative / rock | DIY psych/experimental studios and bar | newriverstudios.com (WP) | **DICE (11)** | easy | high |
| Sebright Arms | Bethnal Green | pop / rock | Basement indie/shoegaze room | sebrightarms.com | **DICE (49)**, includes social:pool/community, so filter on type `music:gig` | easy | high |
| The Old Blue Last | Shoreditch | pop / rock / alternative | Classic upstairs new-band room | — | **DICE (44)** | easy | high |
| The Social | Fitzrovia | pop / alternative | Long-running small indie/electronic bar | thesocial.com (JSON-LD, £) | **DICE (9)** plus own site | easy | med |
| The 100 Club | Oxford St | rock / punk | Historic basement, now a punk/rock/indie institution | the100club.co.uk (WP, DICE links) | **DICE "The 100 Club" (66)** | easy | high |
| The George Tavern | Stepney | alternative / rock / folk | Historic pub venue, saved after a long fight | thegeorgetavern.co.uk (WP, £) | **DICE (49)** | easy | high |
| The Black Heart | Camden | rock (metal/hardcore) | Grassroots metal pub | — | **DICE (49)** | easy | high |
| Electric Ballroom | Camden | rock / pop | Independent 1,500-cap Camden institution (not a chain) | electricballroom.co.uk (WP, See Tickets) | **DICE (38)**: rock/metal/punk; some shows sold on See Tickets only | easy | med |
| The Grace | Highbury | pop / folk / rock | Small upstairs room (ex-Garage sister venue) | site redirects to a linktree shared with The Garage | **DICE "The Grace" (50)** | easy | high |
| The Garage | Highbury | rock / pop | 600-cap rock venue, still open (Songkick shows a full 2026–27 calendar) | linktree only | **Not on DICE.** Probably sells via See Tickets/AXS. Songkick returns 406 to curl | hard | med |
| Islington Assembly Hall | Upper St | pop / rock | Council-owned hall with an indie programme. Larger, but independent | islingtonassemblyhall.co.uk (DICE) | **DICE (66)**; also a DICE venue page with JSON-LD (30 events) | easy | high |
| Union Chapel | Highbury | folk / pop | Working church; folk/indie/jazz concerts | unionchapel.org.uk (/whats-on, 380 KB HTML) | **DICE (55)**: folk/jazz/indie | easy | high |
| Bush Hall | Shepherd's Bush | folk / pop | Edwardian hall with acoustic/singer-songwriter shows | bushhallmusic.co.uk (JSON-LD, See Tickets) | **DICE (18)** plus See Tickets (check the split) | easy/medium | med |
| Hootananny Brixton | Brixton | folk (global/reggae) / club | Reggae, ska, Latin, global sounds; a community pub | hootanannybrixton.co.uk (WP, DICE) | **DICE (32)**: mixed tags (jazz, dnb, hip-hop), so per-event category from genre_tags | easy | high |
| Rich Mix | Bethnal Green | folk (global) / alternative | Independent arts centre, global/diaspora programme | richmix.org.uk (JSON-LD, Skiddle) | DICE (5) only. Its **own site** carries most of the music, so scrape it (JSON-LD present) | medium | med |
| Cafe OTO | Dalston | alternative | World-class experimental/improv room | cafeoto.co.uk (/events/ HTML) | **DICE (14)** plus own site (fuller, HTML) | easy/medium | high |
| Signature Brew (Haggerston / Blackhorse Rd) | Hackney / Walthamstow | rock / pop | Brewery taprooms with grassroots rock bills | signaturebrew.co.uk | **DICE (34 + 23)** as two venues; includes quiz/gaming, so filter on type_tags | easy | med |
| Strongroom | Shoreditch | alternative / pop | Studio-complex bar with small gigs and DJs | strongroombar.com (WP, DICE widget) | **DICE "Strongroom" (31)** | easy | med |
| The Amersham Arms | New Cross | rock / pop | Goldsmiths-area grassroots venue | amershamarms.com (114-byte shell) | DICE "Amersham Arms" (5) only. Thin, so check whether it lists elsewhere | medium | low |
| Dalston Superstore | Dalston | club / alternative (queer) | Queer bar and club institution | dalstonsuperstore.com (WP, JSON-LD) | DICE (9: cabaret/alt-pop). Own site has the full club calendar | medium | med |
| The Fiddler's Elbow | Camden | rock (goth/industrial) | Small Camden pub | thefiddlerselbow.co.uk (Wix) | DICE (4), Skiddle, Eventbrite. Fragmented | medium | low |
| The Lower Third | Soho (Denmark St) | pop / rock | Denmark St basement, emerging bands | — | **DICE (82)** | easy | med |
| The Waiting Room | Stoke Newington | pop / alternative | Tiny basement room | — | **DICE (22)** | easy | med |
| The Hope & Anchor / Water Rats / Fighting Cocks / Dublin Castle | Islington / King's Cross / Kingston / Camden | rock | Classic pub-rock circuit | — | DICE 6 / 6 / 10 / 2: mostly sold on the door or elsewhere. Low coverage | medium | low |
| IKLECTIK / Avalon Cafe | Lambeth / Hackney | alternative | Experimental/noise | — | DICE 4 / 3. IKLECTIK lost its venue (see §3) | — | low |
| Colours Hoxton | Hoxton | pop | Showcase-heavy (industry/label nights). Weaker identity | — | DICE (36) | easy | low |

---

## 2. Aggregator / platform analysis

### DICE (dice.fm): the backbone

- **robots.txt:** `User-agent: * Allow: /` with Cloudflare content signals `search=yes, ai-train=no, use=reference`. No Cloudflare challenge on plain httpx. Our use (listing plus a link back to the ticket page) is "search/reference"-like.
- **Option A, DICE public venue page** `https://dice.fm/venue/<slug>`. Server-rendered Next.js:
  - `__NEXT_DATA__` → `props.pageProps.profile.sections[0].items[].event` gives id, name, `dates.event_start_date/end`, `venues[]` (with address and lat/lng), `price.amount_from` (pence) and status.
  - A JSON-LD `Place` carries an `event[]` list (with `offers.lowPrice`) and the venue's geo coordinates.
  - **First 30 events only** (`load_more: true`). There are **no genre tags** on the venue page, and the event page's `__NEXT_DATA__` exposes only `tags_types` (e.g. `music:gig`).
  - Fully public and the cleanest legitimacy story. 30 events is enough for most small venues (1–3 months).
- **Option B, DICE partner widget API** `GET https://partners-endpoint.dice.fm/api/v2/events?page[size]=100&filter[venues][]=<exact venue name>` with header `x-api-key: <widget key>`.
  - This is what the official "DiceEventListWidget" embed calls from the venue's own site. Venue sites publish their keys in their HTML (MOTH Club's Cargo page has `DICE_KEY = 't7ohtz7E…'`; Strongroom's widget config has `apiKey: 'ZaR9o0Sy…'`, `partnerId: '44a2826c'`).
  - A single key returns events for **any** venue name, with `links.next` pagination.
  - Fields: `name, date, date_end, timezone, venue, address, location, lineup[] (doors/set times), ticket_types[].price.{face_value,total}, price, genre_tags (e.g. gig:indie, gig:punk, dj:techno, party:ukg, comedy:comedy), type_tags (music:gig, music:dj, culture:…), description/raw_description, images, url (link.dice.fm), status, sold_out, external_url`.
  - **Category derivation is easy.** Map from `genre_tags` prefixes and values (dj:*/party:dance → club; gig:punk/metal/rock → rock; gig:indie/pop → pop; gig:folk/world → folk; experimental/noise → alternative). Drop `comedy:*`, `social:*`, `sport:*` and `theatre:*` by type.
  - **Caveat (needs a decision):** using a key a third-party venue embedded is technically easy but not a granted credential. Options: (a) per venue, use that venue's own embedded key (only where it has one); (b) ask DICE for a partner key (they offer one to promoters/partners); (c) use Option A (public venue pages, no genres) and derive category from the venue's list membership. My recommendation: **start with A, ask DICE for a key for B**.
  - Venue-name matching is exact and case-sensitive-ish: "The Shacklewell Arms" (not "Shacklewell Arms"), "The 100 Club", "Windmill Brixton", "Oslo Hackney", "XOYO London", "E1 " (trailing space), "ORMSIDE projects" (returned name). A DICE helper should be keyed on the venue name (or the DICE venue id `venues[].id`, e.g. IAH = 34) per VenueDefinition, so it fits Cartelita's whitelist rule naturally.
- **Shape in Cartelita:** one `dice_london` multi-venue source (`register_source` with ~30 venues) or a generic `DiceVenueScraper` registered 1:1 per venue. The 1:1 form gives per-venue health, and dedup on DICE event id is trivial.

### Resident Advisor (ra.co)

- **HTML pages:** `ra.co/clubs/uk/london` returns **403** (Cloudflare bot block, a 765-byte body) for the Cartelita UA.
- **GraphQL** `POST https://ra.co/graphql` (JSON plus a `Referer: https://ra.co/events/uk/london` header) returns **200** over plain urllib/curl, with no challenge.
  - Query `eventListings(filters:{areas:{eq:13}, listingDate:{gte,lte}}, page, pageSize:100)`, where London is area 13. It returned 592 events for 24–31 Oct.
  - Fields: `event{id,title,date,startTime,endTime,cost,content,contentUrl,venue{id,name},genres{name},artists{name}}`.
  - `cost` is free text ("£", "20", or "": empty on 188/592), which matches Cartelita's price convention. Genres are often present but not always (fabric's sometimes empty).
  - The `club:` filter was ignored in my test, so **filter by `venue.id` client-side**, the same multi-venue whitelist pattern as `jazzin-amsterdam`. It costs about 6–7 requests per nightly run for a week, more for a longer window.
- **robots.txt** disallows `/api/`, `/pro`, `/widget`, but not `/graphql`. RA's terms prohibit automated scraping, and the GraphQL endpoint is unofficial and has changed before. Treat it as **medium-risk / may break**; use it only for club venues DICE doesn't carry.
- RA venue ids found: fabric 237, Phonox 106730, FOLD 155399, Colour Factory 185559, Ormside 108196, M.O.T 156290, The Cause 198121, E1 141756, Village Underground 4567, EartH 150325, XOYO 33592, Ridley Road 59520, Brixton Jamm 1557, Hootananny 143114, Jazz Cafe 1502, Planet Wax 202318, The Glove That Fits 147611, Four Quarters 101865, Low Profile Studios 86422, Sauna Social Club 245698, Club Makossa 117852, Dalston Den 181160, Kings Arms E2 284681, Magazine London 160047, Hackney Church 186122.

### Others

- **Skiddle:** has a public API (`/api/v1/events/search/`), but it **requires an api_key** (400 without one; free registration). XOYO, Rich Mix and Fiddler's Elbow use it. Lower priority, since DICE/RA cover those.
- **Songkick:** returns 406 to curl; the API is closed to new keys. Not viable.
- **See Tickets:** Electric Ballroom and Bush Hall link it. No public API, but the event pages are HTML. Only needed if DICE coverage proves partial.
- **Ents24 / Ticketweb:** not needed given DICE coverage; not probed in depth.
- **Music Venue Trust:** a useful curation list (its Music Venues Alliance membership) but not a data source.

---

## 3. Closures / exclusions

- **Corsica Studios:** closed at the end of March 2026 for refurbishment and soundproofing. The site returns 503 and the venue is absent from RA and DICE. A July 2026 council CPO decision paves the way to stay on site; recheck in 2027.
- **Nambucca (Holloway):** announced closure (still 2 DICE events into November 2026). Exclude.
- **The Borderline (Soho):** announced closure. Exclude.
- **IKLECTIK:** lost its Lambeth space and is running a crowdfunder for a new one. Exclude for now.
- **The Gun (Hackney):** closed. **Jumbo, Two Palms:** nothing found on DICE, RA or the web. Treat as inactive.
- **MOTH Club:** at risk but open. One development refused in March 2026, a second application pending.
- **Excluded on curation grounds:** O2 Academy Islington/Brixton (chain), KOKO (large, commercial), Ministry of Sound, Drumsheds, Printworks-style megavenues, Egg, Lightbox/Cable/Soul Lounge-style party brands, and Boisdale and similar venues. **Borderline:** E1 and XOYO (big, increasingly generic).
- Dead or missing own domains (venues alive, use platform data): colourfactory.london, venuemot.*, e1ldn.com, thevictoriadalston.com, sebrightarms.co.uk. Oslo and The Garage/Grace now redirect to linktree.

---

## 4. Recommended starter set (about 20 venues, 2 sources)

**Build first: one `DiceVenueScraper`**, keyed on the DICE venue name or id per venue. Use the public venue page (Option A) until a partner key is sorted.

- **club:** Phonox, Colour Factory, FOLD (merge with RA), Village Underground
- **pop:** MOTH Club, The Lexington, Oslo Hackney, The Shacklewell Arms, Paper Dress Vintage, Sebright Arms, The Old Blue Last, Islington Assembly Hall
- **rock:** The 100 Club, The George Tavern, The Black Heart, Electric Ballroom
- **alternative:** EartH, New River Studios, Cafe OTO
- **folk/global:** Union Chapel, Hootananny Brixton

**Second: one `ra_london` multi-venue source** (GraphQL, area 13, venue-id whitelist) for the clubs DICE misses: fabric (237), Venue MOT (156290), Ormside Projects (108196), The Cause (198121), plus Planet Wax, The Glove That Fits, Four Quarters or Low Profile Studios as further grassroots club picks. Flag its unofficial status in the SOURCE.md.

**Third: own-site scrapers** where DICE is partial: Windmill Brixton (many door-only shows), Rich Mix (global programme), Dalston Superstore, Cafe OTO (fuller programme).

**Later / low priority:** The Garage (See Tickets/AXS), Rye Wax (Wix), Amersham Arms, Fiddler's Elbow, the pub-rock circuit (Hope & Anchor, Water Rats, Dublin Castle).
