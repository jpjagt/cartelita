# London — jazz & experimental/improv venue research (2026-10-24)

All probes used the Cartelita UA, plain curl (httpx-equivalent) unless noted. `cffi` = `curl_cffi impersonate="chrome"`.
Note: a few hosts (e.g. jazzinlondon.net, hundredyearsgallery.co.uk, totalrefreshmentcentre.com) timed out on :443 from this machine but answered on :80; worth re-checking from prod.

## 1. Venue table

| Venue | Area | Fit | URL | Data source + platform | Scrapeability | Confidence |
|---|---|---|---|---|---|---|
| **Cafe OTO** | Dalston E8 | Core. London's experimental/free-improv home; residencies (Evan Parker matinees), members' prices. | https://www.cafeoto.co.uk/events/ | Server HTML list (date, time, title, full price ladder "£17 / £15 Adv / £10 members"); per-event pages; also `/events/day/YYYY/MM/DD`. DICE for ticketing. robots: `Crawl-delay: 10`. | easy | high |
| **Vortex Jazz Club** | Dalston N16 | Core. Non-profit, volunteer-run, regulars, free Sunday jam (`vortex-jam-session`), downstairs Whirlpool sessions. | https://www.vortexjazz.co.uk/events/ | WordPress + The Events Calendar (tribe) theme but **REST API disabled** (`rest_no_route`). Day pages `/events/YYYY-MM-DD/` are server HTML with time + full price text ("Standard £25 / Members £23"). Tickets via universe.com. Also on jazzlondonlive (37 events/Oct). | easy | high |
| **Hundred Years Gallery** | Hoxton E2 | Core experimental/free-improv (Steve Noble, Mark Wastell residency, KNOT series); tiny, regulars. Also exhibitions/books (filter "Music :" / "Residency :" prefix). | http://hundredyearsgallery.co.uk/events/upcoming/ | WordPress, single server-HTML "Upcoming" list with "Music : Title. Day Nth Month HH:MM". No price on list (check detail page). HTTPS timed out here; HTTP works. | easy | high |
| **IKLECTIK** | Peckham Levels SE15 (was Old Paradise Yard) | Good: experimental/electronic/noise. **Risk:** Peckham Levels was a 13-month residency from Oct 2025 — may move/end ~Nov 2026. | https://www.iklectik.org/ | Wix site, events rendered server-side with date/time/price ("£11.30"), DICE ticket links. Wix markup is brittle; DICE event pages are an alternative. | medium | medium |
| **Ronnie Scott's** | Soho W1 | Institution; touristy main shows but Late Late Show / Upstairs jam-ish sessions are the regulars' thing. Include, perhaps whitelist-light. | https://www.ronniescotts.co.uk/find-a-show | **Cloudflare 403 with httpx; passes with cffi.** `/find-a-show?order=show-date&when=all` server HTML, paginated (`loadmore=1`), residencies shown as date ranges → need detail pages for per-night times; detail has thin JSON-LD MusicEvent (no offers). Prices not on list. Alternative: jazzlondonlive lists every Ronnie's show with time (137/Oct, no prices). | medium (cffi) | high |
| **PizzaExpress Jazz Club Soho** | Soho W1 | Long-running basement club, mainstream; many tribute acts (curate lightly). | https://www.pizzaexpresslive.com/whats-on | Next.js shell; clean **JSON API** `https://api.pizzaexpresslive.com/products/search-event-information?page=N` (hydra, 321 items; name, slug, price in pence, eventDate, doors/show time, `location: "Soho"/"Holborn"…`). No auth. | easy | high |
| **606 Club** | Chelsea SW10 | Musicians' club since 1976, UK-scene programming; but dinner required for non-members (borderline "dinner show"). | https://www.606club.co.uk/booking/ | Custom PHP; calendar via `/events-ajax-calendar/?d=YYYY-MM-DD&...` (HTML fragments). Prices on separate "Times :: Prices" page. Fully covered by jazzlondonlive with prices (35/Oct). | medium | high |
| **Toulouse Lautrec** | Kennington SE11 | Good: jazz club + free/cheap jam sessions (blues, funk, Latin, New Orleans jams), "Jazz Ladder" for young players. Also a restaurant. | https://toulouselautrec.co.uk/whats-on/ | WordPress, server HTML list (paginated `?query-…-page=2`), detail `/event_calendar/<slug>/`; tickets on **Ticket Tailor** (`tickets.toulouselautrec.co.uk/all-tickets-calendar/...`). robots open. On jazzlondonlive (25/Oct, prices). | medium | high |
| **Jamboree** | King's Cross WC1 | Great fit: free weekly sessions (Celtic, swing, Balkan/Klezmer jams), world/folk/jazz. Overlaps folk scope. | https://www.jamboreevenue.co.uk/upcoming-events/ | WordPress; on jazzlondonlive (19/Oct with prices). Not deep-probed. | easy–medium | medium |
| **Ninety One Living Room** | Brick Lane E1 | Good: contemporary UK jazz, Jazz re:freshed Thursdays, Brick Lane Jazz Festival. | https://91livingroom.com/whats-on/ | WordPress page embedding the **DICE event-list widget** (partnerId + public apiKey). The partners endpoint answered but returned global DICE events; venue scoping not yet worked out. jazzlondonlive only lists ~4/month. (91livingroom.com, not ninetyonelivingroom.com which has no DNS.) | medium | medium |
| **Spice of Life** | Soho W1 | Mixed pub programme; the jazz parts fit well: Monday Spice of Life Jazz Club, **Sunday 1pm Jazz Notes jam**, Monday blues & jazz jam, Friday lunchtime jazz. Needs title/keyword whitelist (also comedy, indie). | https://www.spiceoflifesoho.com/events/ | WordPress server HTML list (title + date; recurring entries "Every Sunday"); tickets ticketool/wegottickets. | easy (filtering needed) | high |
| **Jazzlive at the Crypt** | Camberwell SE5 | Great fit: volunteer-run Friday club in a church crypt since 1995, cheap, regulars. | https://www.jazzlive.co.uk/ | Static HTML "Upcoming Events" list (date + artist; fixed doors 20:00 / first set 21:15). Price on tickets page. | easy | high |
| **Jazz Cafe POSK** | Hammersmith W6 | Good community club (Polish centre), Fri/Sat, door prices. | https://jazzcafeposk.org/gig-guide/ | WordPress server HTML with date + price ("£15 on the door and Eventbrite"). | easy | high |
| **Blue Note London** | (new 2025/26 club) | Big-name, ticketed, dinner-club format; on the edge of the curation test, but serious programming (Glasper residency, Levitation Orchestra). | https://www.bluenotejazz.com/london/shows/ | WordPress, server HTML (date, title, set times). On jazzlondonlive (62/Oct). | easy | medium |
| **Kings Place (jazz strand)** | King's Cross N1 | Concert hall; good jazz series (Edition Records, KP Jazz Orchestra), not a hangout. | https://www.kingsplace.co.uk/whats-on/jazz/ | **httpx 403 (bot wall); cffi 200.** Server HTML list with date/time; **Spektrix** ticketing (`ticketing.purchase.kingsplace.co.uk`). | medium (cffi) | high |
| **The Jazz Cafe** | Camden NW1 | Mostly soul/hip-hop/club nights despite the name; a "Jazz & Improvised Music" genre filter exists. Better in a club/soul category. | https://thejazzcafe.com/whats-on/ | WordPress server HTML list, `/event/<slug>/` pages, genre filter. | easy | high |
| **Bull's Head, Barnes** | Barnes SW13 | Historic jazz room (now Young's pub); only ~6 jazz nights/month on jazzlondonlive. | https://www.thebullsheadbarnes.com/whats-on | Propeller-built pub site, JSON-LD `Event` (3 items, mostly pub events). Use aggregator. | medium | medium |
| **Morocco Bound (SE1 / SW18)** | Bermondsey / Wandsworth | Good: bookshop-bar, improv ensembles (NOISE), cheap/concession. | https://www.moroccobound.co.uk/whatsonbermondsey | Wix; on jazzlondonlive. | medium (use aggregator) | medium |
| **Karamel Club, The Archduke, sYp, Fox & Firkin, Green Note, East Side Jazz Club…** | various | Local pub/club jazz nights, many **free** (Archduke, sYp). Exactly the long tail an aggregator gives you. | — | Only via jazzlondonlive. | easy (via aggregator) | medium |
| **Church of Sound** | Clapton E5 | Great fit (songbook series in St James the Great church, 10th birthday 20 Nov 2026 at Barbican/EFG) but **irregular** (roughly monthly). | (no working site: churchofsound.com redirects to an unrelated domain) | DICE / Instagram only. | hard | medium |
| **Steam Down** | SE London (Peckham Levels in 2025) | Ideal in spirit (weekly community session) but 2026 weekly venue unconfirmed; site's /tickets 404. | https://www.steamdown.co.uk/ | Squarespace, no listings. | hard / skip for now | low |
| **Oliver's Jazz Bar** | Greenwich SE10 | Nightly basement jazz + jams historically. Listed by Visit Greenwich for 2026, but **oliversjazzbar.co.uk is now a spam/SEO blog** and it's absent from jazzlondonlive. | — | No usable source (Fever listing only). | blocked (no source) | low |
| **Brilliant Corners** | Dalston E8 | Listening bar — calendar is almost all **DJs**, not live jazz. Out of jazz scope (maybe "club"). | https://brilliantcornerslondon.co.uk/dates/ | WordPress, server HTML (date + DJ name). | easy | high |
| **Ridley Road Market Bar** | Dalston | DJ/party bar, no jazz programming. | — | Wix. | n/a | high |
| **EFG London Jazz Festival** | citywide, 13–22 Nov | Annual; events are hosted at venues already above + Barbican/RFH. Best handled as a **festival list / annotation**, not a venue. | https://efglondonjazzfestival.org.uk/ | Spektrix + server HTML `/events/<slug>` pages, some JSON-LD. | medium | high |

## 2. Aggregator analysis

### JAZZLONDONLIVE (jazzlondonlive.com) — recommended single mainstream-jazz source
- Run by Sarah Chaplin (Jazz London Live Ltd), app + newsletter; claims ~500+ gigs/month. **October 2026: 728 events, ~85 distinct venues.**
- **Structure (server HTML, no JS, no Cloudflare, robots.txt 404 = no rules):**
  - `/jazz-dates` = current month, all events in one page: `<h3><span class="text-white">DD/MM/YYYY HH:MM {venue name} {price}</span><a href="{event/booking url}"><span>{title}</span></a>`.
  - `/events_by_month/YYYY/M` = that month's **venue index** (links to the per-venue month pages), archive back to Jan 2022. (Re-checked 2026-10-24: the events themselves are on `/jazz-dates` and the per-venue pages, not here.)
  - `/venue/YYYY/MM/{id}` = per-venue month page (stable numeric venue IDs, e.g. 2 = 606 Club, 59 = Ronnie's, 75 = Vortex). Homepage lists venues with IDs.
  - Price is free text ("£18", "Free", "£12 / 8 concession", "£9 - 22 advance"); missing for ~230/728 (Ronnie's, Blue Note publish none); 68 are free.
  - Each row links out to the venue's own event/booking page → usable as `source_url`; no external IDs, so dedup tier 2 (source_url) or tier 3 (title+date). Some links are junk (`http://`).
- **Big caveat — horizon:** it's hand-compiled **per month**. On 24 Oct, November is still empty (`/jazz-dates` holds only October: 728 events, 177 of them from the 24th on; `/venue/2026/11/{id}` is empty for Vortex, Ronnie's and 606). So near month-end the agenda has only a few days of future data; the health system would see "coverage drop" every month until the next month posts. Needs a source-level rule tolerant of that, or pair with per-venue scrapers for the anchors.
- **Coverage skew:** strong on mainstream/straight-ahead/supper-club and suburban/home-counties jazz clubs (Luton, Guildford, Southend, Eastbourne… must be **denylisted**, like jazzin's postcode gate — venue names carry the town). Weak on the experimental/new-UK-jazz scene: **no Cafe OTO, IKLECTIK, Hundred Years Gallery, Church of Sound**; only 4/month for 91 Living Room; misses Spice of Life's weekly jams. Also lists big halls (Royal Albert Hall, Cadogan, Wigmore, O2 Academy) to exclude.
- Verdict: works as the jazzin.amsterdam-style whitelist source for ~30–40 London venues (exact venue-name matching), but **not** as the whole jazz category; add per-venue scrapers for the experimental venues and possibly for the anchors (Vortex, Cafe OTO).

### jazzinlondon.net ("Jazz in London", Mary Greig's guide since 1971) — dead
- Domain **expired** (Namecheap parking page, Oct 2026). Not usable.

### London Jazz News → UK Jazz News (ukjazznews.com)
- Now news/reviews/previews only (WordPress); no structured gig listings. Not a source.

### Jazz Near You (jazznearyou.com/london)
- Global jazz calendar with London pages; **Cloudflare JS challenge (403)** and a robots.txt with Content-Signals. Skip.

### Jazzwise gig guide
- Monthly magazine page, national, often stale (cached copies from 2024). Not a source.

### "London Jazz Collective", "Where's the Jazz", Mulberry
- No live listing site found for any of these. Not sources.

### General platforms (DICE, Skiddle, EventsList, Songkick)
- DICE London jazz browse covers the newer scene (OTO, IKLECTIK, 91, Church of Sound use DICE), but it's a commercial ticketing platform, not editorial; per-venue DICE pages/widgets are the better hook. EventsList/Skiddle are SEO aggregators — skip.

## 3. Exclusions / closures

| Venue | Status | Reason |
|---|---|---|
| Kansas Smitty's (Broadway Market) | **Closed** (2020, pandemic) | Site 404; house band carries on elsewhere. |
| Mau Mau Bar (Portobello Rd) | **Closed** (Feb 2020) | Jazz re:freshed moved on (now at 91 Living Room). mau-mau.co.uk is an unrelated artist shop. |
| Total Refreshment Centre (Stoke Newington) | **Gigs stopped** | Council closure notice (licensing); domain expired 30/09/2026. |
| Matchstick Piehouse (Deptford) | Closed end 2023; co-op reopening planned spring 2025, unconfirmed | Both .com/.co.uk have no DNS. Re-check later. |
| Servant Jazz Quarters (Dalston) | Open, but now mostly indie/singer-songwriter gigs; domain has no DNS | Not a jazz programme. |
| Oliver's Jazz Bar (Greenwich) | Possibly open, but no usable data source | Domain turned into a spam blog; absent from aggregator. |
| Brilliant Corners, Ridley Road Market Bar | Open | DJ / listening bars, not live jazz. |
| Steam Down | Active collective, weekly venue for 2026 unconfirmed | No listings on its site. |
| Church of Sound | Active, irregular | No site; DICE only. Revisit with a DICE-based helper. |
| Pelican (Peckham)/"Steam Down at the Pelican" | Not found as an active 2026 jazz venue | — |
| The Elgar Room (Royal Albert Hall) | RAH appears on jazzlondonlive as one-offs | Hall programming, not a club; exclude. |
| Home-counties clubs on jazzlondonlive (Luton Bear Club, Guildford, Southend, Eastbourne, Maidenhead, Dorking, Fleet, Harlow, Brentwood, Bracknell, Cambridge) | — | Outside London — denylist. |
| Big halls (Royal Albert Hall, Cadogan, Wigmore, O2 Academy, Barbican one-offs), Boisdale (£79 dinner shows), Crazy Coqs, The Pheasantry | — | Touristic/dinner-show/concert-hall; don't whitelist by default. |

## 4. Recommended starter set

1. **jazzlondonlive** multi-venue source (whitelist, exact names), initially ~20–25 venues: Ronnie Scott's, Vortex, 606 Club, PizzaExpress Jazz Club Soho, Toulouse Lautrec, Jamboree, Jazz Cafe POSK, Jazzlive at the Crypt, 91 Living Room, Spice of Life, Bull's Head Barnes, Morocco Bound (both), Karamel Club, The Archduke, sYp, Fox & Firkin, Green Note, East Side Jazz Club, The Woodman, Clapham Common Jazz Club, Blue Note London (optional), Kings Place (optional). Denylist out-of-London + halls + Boisdale/supper clubs. Plan for the month-boundary horizon in health checks.
2. **Cafe OTO** — own scraper (easy server HTML, prices; respect crawl-delay 10s).
3. **Hundred Years Gallery** — own scraper (easy single page; filter "Music"/"Residency").
4. **IKLECTIK** — own scraper (Wix server HTML or DICE), flagged as at-risk venue.
5. Later / optional per-venue upgrades where the aggregator is thin: Vortex day pages (better descriptions/prices, jam sessions), Spice of Life (weekly jams), 91 Living Room (DICE widget), Ronnie's via cffi (descriptions), PizzaExpress JSON API (prices, trivial).
6. Treat **EFG London Jazz Festival** (13–22 Nov) as a festival annotation/list rather than a venue.
