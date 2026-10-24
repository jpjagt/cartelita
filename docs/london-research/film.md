# London — FILM venues for Cartelita (research, 2026-10-24)

Method: live probes with the Cartelita UA (curl), plus `curl_cffi impersonate="chrome"`
where curl got 403. Showing counts and "furthest date" come from Clusterflick's
`combined-data.json` release `20261023.171652`. Platform notes are taken from
Clusterflick's open-source per-cinema retrievers (`clusterflick/scripts/cinemas/<id>/retrieve.js`),
which document how each site is scraped. Every venue below has live showings in
that dataset, so all of them are active in Oct 2026.

## 1. Venue table

Verdict key: **easy** = server HTML or an open JSON endpoint, plain httpx.
**medium** = several requests, a token or GraphQL, or curl_cffi needed.
**hard** = browser, or brittle/sparse data. **blocked** = no workable path.

| Venue | Area | Why it fits (or not) | URL | Data source found + platform | Verdict | Conf. |
|---|---|---|---|---|---|---|
| BFI Southbank | South Bank | The national cinematheque: seasons, 35/70mm, repertory. A must. | whatson.bfi.org.uk | AudienceView "Online" box office. **Cloudflare 403 to curl; 200 with curl_cffi.** Listing HTML has `articleContext`/`searchResults` JS blobs with times. Clusterflick uses Playwright plus a request delay. 382 showings (season window ~5 weeks). Prices are on the event pages. | medium (curl_cffi; browser fallback) | high |
| Prince Charles Cinema | Leicester Sq (West End) | Repertory/cult, sing-alongs, all-nighters, 35/70mm. Famous for its regulars. | princecharlescinema.com/whats-on/ | WordPress. The whole programme is in one 1.6 MB server-HTML page; prices visible (£). Cloudflare headers but no challenge (200). 694 showings. | easy | high |
| Rio Cinema | Dalston | Community-owned single-screen indie. Strong identity. | riocinema.org.uk/Rio.dll/WhatsOn | **Savoy Systems.** `<script>var Events = {...}</script>` JSON in the WhatsOn HTML: Title, Synopsis, URL, Performances[StartDate…]. Only PriceGroupID, no price string. | easy | high |
| Genesis Cinema | Whitechapel/Mile End | Independent, cheap tickets, local programme. | genesiscinema.co.uk | **Admit One** (genesis.admit-one.co.uk). Showtimes are in server HTML. Price not on the listing. | easy | high |
| Close-Up Film Centre | Shoreditch | Cinephile repertory with a film library. Best-in-class curation. | closeupfilmcentre.com | Custom PHP. The homepage has embedded JSON: `show_time`, `film_url`, TicketSource booking URL. 200 to curl. Clusterflick escalates to Camoufox, so it is sometimes protected. No price. | easy–medium | high |
| ICA | The Mall | Arthouse/artists' film, ICA programme. | ica.art/upcoming | Server HTML, `.item.films` cards, then per-film pages. Spektrix for ticketing. 139 showings. | easy | high |
| Barbican Cinema | City | Big arts-centre cinema; seasons, festivals, Q&As. Fits with a cinema whitelist. | barbican.org.uk/whats-on/cinema | Drupal. Server HTML listing (`.listing--event`) plus `/whats-on/event/{id}/performances` fragments. Spektrix. Cloudflare present but returned 200. | medium (multi-request) | high |
| The Garden Cinema | Covent Garden | Independent arthouse/repertory, opened 2022. Exactly on-brief. | thegardencinema.co.uk | WordPress. All screenings are in server HTML (`screening-panel` per day). Savoy for booking/images. Some price text (transform parses it). | easy | high |
| The Castle Cinema | Homerton | Crowdfunded community indie. | thecastlecinema.com | Server HTML. `data-start-time` ISO plus `data-perf-id`; price labels ("£6 Monday!") are visible. No Cloudflare. | easy | high |
| Rich Mix | Shoreditch | Community arts centre. The film programme is mostly mainstream releases plus some events. Marginal. | richmix.org.uk/cinema/ | WP, server HTML cards, Spektrix. Only 7 items in Clusterflick. | easy | medium |
| Phoenix Cinema | East Finchley | Historic 1910 charitable indie. | phoenixcinema.co.uk/PhoenixCinemaLondon.dll/WhatsOn | **Savoy**: same `var Events` JSON as the Rio. | easy | high |
| Electric Cinema (Portobello / White City) | Notting Hill / White City | Historic luxury cinema (Soho House). Mostly first-run; low curation. | electriccinema.co.uk/portobello | JS front end with an `/api/` reference; Clusterflick has a shared retriever. | medium | medium |
| The Lexi | Kensal Rise | Volunteer-run social-enterprise cinema. | thelexicinema.co.uk/TheLexiCinema.dll/WhatsOn | **Savoy** `var Events` JSON. | easy | high |
| The Cinema Museum | Kennington | Archive/heritage screenings, silent film, talks. Strong identity. Running a "Buy Our Home" campaign (2026) to secure the building. | cinemamuseum.org.uk/schedule/ | WordPress + The Events Calendar (Tribe). **JSON-LD Event with `offers.price`** in server HTML (Tribe REST `/wp-json/tribe/events/v1/events` is likely too). Cloudflare; Clusterflick escalates to Camoufox at times. | easy–medium | high |
| Regent Street Cinema | Marylebone | Birthplace of UK cinema (University of Westminster). Repertory and events. | regentstreetcinema.com | **Indy Cinema Group** SPA. POST `/graphql` with `client-type: consumer` and a `site_id` cookie (verified: endpoint answers, needs the site id). | medium | high |
| Ciné Lumière (Institut français) | South Kensington | French/world cinema, festivals. Cultural institute. | institut-francais.org.uk/cinema/ | WP server HTML (`article.card--film`), then film pages. Booking via Savoy (cinelumiere.savoysystems.co.uk). 284 showings. | easy | high |
| Goethe-Institut London | South Kensington | German film screenings; very sparse (7 in the current window). | goethe.de/ins/gb/en/ver.cfm | **403 to curl, 200 with curl_cffi.** Generic events calendar. | medium; low value | medium |
| JW3 | Finchley Road | Jewish cultural centre cinema, UKJFF host. Mixed programme. | jw3.org.uk/whats-on/cinema | **403 to curl (non-CF WAF), 200 with curl_cffi.** Spektrix connector; Clusterflick uses Camoufox plus Spektrix. | medium | medium |
| ArtHouse Crouch End | Crouch End | Independent arthouse. | arthousecrouchend.co.uk | WP/Elementor. `.performance` blocks in server HTML; Savoy booking links. | easy | high |
| Curzon (Soho, Bloomsbury, Aldgate, Hoxton, Camden, Mayfair, Victoria…) | various | Arthouse chain (Curzon Soho/Bloomsbury are institutions; **Bertha DocHouse** is the documentary screen inside Curzon Bloomsbury). Include with whitelist. | curzon.com/venues/soho/ | **Vista OCAPI v1.** Cloudflare 403 to curl, 200 with curl_cffi. The page HTML carries `authToken` plus the Vista API base; `/api/omnia/v1/page?friendly=…` returns the venue node. Clusterflick: Playwright to bootstrap, then OCAPI (Camoufox fallback). | medium–hard | high |
| Picturehouse (Hackney, Ritzy, Gate, Central, Crouch End…) | various | Cineworld-owned chain, mostly first-run with some seasons. Ritzy/Hackney have local identity. Optional, whitelisted. | picturehouses.com | **Open Vista-backed JSON:** `POST /api/get-movies-ajax` with `start_date=show_all_dates&cinema_id=010`. Verified 200, 5 MB, **every Picturehouse at once** (Showtime, ScreenName, SoldoutStatus, attributes). No price. | easy | high |
| Everyman (Hampstead, Screen on the Green…) | various | Premium-sofa chain, first-run. Low curation fit. | everymancinema.com | Webedia Gatsby + Boxoffice API (`page-data/sq/d/*.json`). Cloudflare but 200. | medium | high |
| **The Nickel** (extra) | Clerkenwell | Tiny cult/grindhouse repertory bar-cinema. Very on-brief. | thenickel.co.uk | Next-style SSR: `initialScreenings` JSON in the HTML (date, filmTime, capacity, ticketsSold, format) plus a per-screening JSON API. | easy | high |
| **The Arzner** (extra) | Bermondsey | LGBTQ+ community cinema (opened 2025). | thearzner.com/TheArzner.dll/WhatsOn | **Savoy** `var Events` JSON. 134 showings. | easy | high |
| **ActOne** (extra) | Acton | Independent neighbourhood cinema. | actonecinema.co.uk/ActOneCinema.dll/WhatsOn | **Savoy.** | easy | high |
| **Kiln Theatre cinema** (extra) | Kilburn | Theatre with an arthouse cinema. | kilntheatre.com/cinema-listings/ | Server HTML; Spektrix. | easy | medium |
| **The Horse Hospital** (extra) | Bloomsbury | Underground/avant-garde film and arts. | thehorsehospital.com/events?category=Film | Squarespace-style server HTML events. | easy | medium |
| **David Lean Cinema** (extra) | Croydon | Volunteer-run community cinema. Outer London. | davidleancinema.ticketsolve.com/shows.xml | **Ticketsolve XML feed** (open, 200). | easy | high |
| **Olympic Cinema** (extra) | Barnes | Independent, upmarket, first-run-ish. | olympiccinema.com/whats-on | Server HTML plus `/api/`; price visible. | easy | medium |
| **Sands Films Cinema Club** (extra) | Rotherhithe | Film-studio cinema club (Christine Edzard). Sparse. | sandsfilms.eventive.org | **Eventive** (open JSON). | easy | medium |
| **Birkbeck Cinema / BLOC (QMUL)** (extra) | Bloomsbury / Mile End | University cinemas, free screenings. Sparse. | bbk.ac.uk/events?tag=30 | University event pages. | easy; low volume | medium |
| Coldharbour Blue (extra) | Brixton/Loughborough Jn | Small indie bar-cinema. | coldharbourblue.com/events | Tribe Events (WP REST). | easy | medium |

Notes on price: only these show a usable free-text price on the listing: Castle,
Prince Charles, Cinema Museum (JSON-LD), Olympic, and Garden (in the text). The Savoy,
Picturehouse, Vista and Admit One sources only give price groups or nothing. Leave
price empty there. Per the null guard that is fine.

## 2. Aggregator analysis

### Clusterflick (clusterflick.com): strongly recommended as a reference, debatable as a single source

- **What it is:** an open-source pipeline ("every film showing in London"). GitHub org
  `clusterflick`, all code **MIT**. The stages are separate repos (`data-retrieved` →
  `data-transformed` → `data-combined` → `data-matched`), run on GitHub Actions.
  The site is a Next.js static export.
- **Output:** GitHub **release assets**, published several times a day (e.g.
  8 `data-combined` releases between 21 and 23 Oct).
  - `https://github.com/clusterflick/data-combined/releases/latest/download/combined-data.json`
    (25 MB): `{venues{477}, movies{~2000}, people, genres, collections, generatedAt}`.
    Each movie has `performances[]` (`time` epoch ms, `bookingUrl`, `screen`,
    `notes` such as "Part of <season>", `status.soldOut`, `format` 35mm/70mm,
    `accessibility`) and `showings{venueId, url, category, overview}`. Venues carry
    address, **geo lat/lon**, type and programming.
  - `data-transformed` releases have **one asset per venue** (e.g. `.../riocinema.org.uk`),
    so a source can pull one venue's file. Each record has the raw venue `title`,
    `url`, performances, and a TMDB summary.
- **Coverage:** 477 venues, 290 with showings now, ~45,700 performances. That is every
  candidate above plus Cineworld/Vue/ODEON, pubs, libraries and pop-ups.
  The windows match the venues' own (BFI ~5 weeks, others months ahead).
- **Gaps for Cartelita:** **no price** field anywhere. No venue-written synopsis
  (only TMDB overview); event titles are sometimes normalised to TMDB titles in
  `combined`, while `transformed` keeps the raw title. It also depends on a third party's CI
  staying green; it has an active health-probe culture, but if it lapses, all of London film goes dark.
  **Data licence:** the repos are MIT for code; the scraped listing data has no explicit
  licence. Credit Clusterflick and ask the maintainer before relying on it.
- **Verdict:** the best design is **a multi-venue `clusterflick` source** (aggregator =
  editorial whitelist) that reads the per-venue `data-transformed` assets, or `combined`,
  for the curated venues. It is one HTTP fetch per venue, needs no Cloudflare/Playwright work
  for BFI/Curzon/Close-Up/Cinema Museum, and provides lat/lon. Write **venue-direct
  scrapers** only where we want price/descriptions or independence: Castle, Prince
  Charles, Cinema Museum, Garden, and the Savoy cluster, which is one shared parser.
  The hard ones (BFI, Curzon, JW3) are the strongest argument for Clusterflick:
  it already pays the browser/camoufox cost.

### Platform "APIs" worth knowing

- **Savoy Systems** (`*.dll/WhatsOn`): `var Events = {…}` JSON inline. One parser covers
  Rio, Phoenix, Lexi, Arzner, ActOne (and Ciné Lumière/Garden booking). Highest leverage.
- **Picturehouse:** `POST /api/get-movies-ajax` returns all sites, open JSON.
- **Curzon:** Vista OCAPI v1. The bearer `authToken` and API base are embedded in the venue page (curl_cffi).
- **Everyman:** Boxoffice API via Gatsby `page-data` static JSON.
- **Indy Cinema Group** (Regent Street): `/graphql` with a `site_id` cookie.
- **Spektrix** (ICA, Barbican, Kiln, Rich Mix, JW3): only the web components are exposed. Parse the venue's own HTML instead.
- **Admit One** (Genesis), **Ticketsolve** XML (David Lean), **Eventive** JSON (Sands, festivals such as UKJFF), **TicketSource** (Close-Up booking).

## 3. Exclusions

- **Cineworld, Vue, ODEON, Omniplex, Lumiere Romford, Peckhamplex, Science Museum IMAX, BFI IMAX:** mainstream multiplex/blockbuster programming; fails "made for the people who live here".
- **Everyman, Electric:** premium first-run chains with little curation. Exclude, or add later with a tight whitelist.
- **Rooftop Cinema Club, Backyard Cinema, Canary Wharf Summer Screens, hotel screening rooms:** seasonal or touristic experiences.
- **Goethe-Institut:** a handful of screenings a month, plus a 403 without curl_cffi. Low value; reachable through Clusterflick if wanted.
- **Rich Mix (film):** a mostly mainstream film slate, few items. Reconsider as a multi-category arts venue later.
- **Deptford Cinema:** conflicting reports (Wikipedia lists a 2020 closure) and it is not in Clusterflick. Not verified active.
- **Curzon outer sites (Kingston, Wimbledon, Richmond, Sea Containers):** outer/hotel sites. Start with Soho, Bloomsbury (+DocHouse), Aldgate and Hoxton.

## 4. Recommended starter set (~14 venues)

Core, venue-direct and easy (Savoy parser + HTML):
1. Prince Charles Cinema (HTML, price)
2. The Garden Cinema (HTML)
3. Rio Cinema (Savoy)
4. Phoenix Cinema (Savoy)
5. The Lexi (Savoy)
6. The Arzner (Savoy)
7. The Castle Cinema (HTML, price)
8. Close-Up Film Centre (embedded JSON)
9. ICA (HTML)
10. Genesis (Admit One HTML)
11. The Nickel (embedded JSON)
12. The Cinema Museum (JSON-LD with price)

Harder but essential: **BFI Southbank** (curl_cffi) and **Curzon Soho + Bloomsbury
(+ Bertha DocHouse)** (curl_cffi + OCAPI). Either take these from **Clusterflick**
(a multi-venue source whitelisted to just these) or build them direct after the core.

Second wave: Barbican Cinema, Ciné Lumière, Regent Street Cinema, ArtHouse Crouch End,
Kiln, Horse Hospital, JW3, and Picturehouse Ritzy/Hackney (one open JSON call) if we
want neighbourhood first-run houses.

Alternative plan with the least code: a single `clusterflick` source for all of the
above, accepting no prices. Then replace venues with direct scrapers one at a time
where price or description matters. Ask the Clusterflick maintainer first.
