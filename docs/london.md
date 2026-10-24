# London — venue research and build plan

Date: 2026-10-24. Status: **research only, nothing built.** Per-genre raw
notes (every probe result, Spektrix client bases, DICE venue names, RA venue
ids) are in `docs/london-research/`. Every venue below
was probed live (curl with the Cartelita UA; `curl_cffi impersonate="chrome"`
where noted as *cffi*) and checked for 2026 activity. Rules carry over from
`docs/nl-cities-plan.md`: curation over exhaustiveness, categories only from
the source's own structural labels (never title keywords, every exclusion
recorded in SOURCE.md), one owning source per venue, globally unique venue
slugs, honest UA, the `writing-a-scraper` skill.

## The structural finding: London is a platform city

Yerevan was "a few aggregators + Instagram"; Rotterdam/Utrecht were mostly
one scraper per venue. London is neither: the scene sits on a handful of
ticketing platforms, several with open JSON, so **six shared helpers cover
~80% of a strong starter set.**

| Platform | What's open | London venues on it | Helper |
|---|---|---|---|
| **Spektrix** | Public v3 API, no auth, no Cloudflare, answered for every one of ~45 clients tested: `/{client}/api/v3/events?instanceStart_from=…` (client-defined `attribute_*` genre fields), `/instances?startFrom=…` (**one row per performance**, `cancelled`), `/instances/{id}/price-list` (real £ amounts; cache by `priceList.id`) | Royal Court, Young Vic, Bush, Donmar, Soho Theatre, Kiln, Arcola, Park, Orange Tree, CPT, The Yard, Southwark Playhouse, Theatre503, Brixton House, Lyric Hammersmith, BAC, Stratford East, Coronet, The Place, Unicorn, Little Angel, Polka, Barbican, Sinfonia Smith Square, St Martin-in-the-Fields, Cadogan Hall, RCM, RAM, Blackheath Halls/Trinity Laban, Cecil Sharp House, Kings Place, ENO, Opera Holland Park, Rich Mix, Jacksons Lane, Riverside… | `_spektrix.py`: config per venue = `(base url, attribute → category map, exclusion attrs)` |
| **DICE** | (a) Partner widget API `partners-endpoint.dice.fm/api/v2/events?filter[venues][]=<exact name>` + `x-api-key` — genre tags, set times, ticket prices, full list; (b) public venue pages `dice.fm/venue/<slug>`: `__NEXT_DATA__` + JSON-LD (dates, price, coords; next 30 events, **no genre tags**). robots `Allow: /` | ~40 grassroots gig/club venues: MOTH, Lexington, Oslo, Shacklewell, Windmill, 100 Club, George Tavern, EartH, Village Underground, Phonox, FOLD, Colour Factory, Union Chapel, Hootananny… | `_dice.py`, 1:1 per venue (per-venue health); (a) with the venue's own key where it embeds one, else (b) — see Decisions |
| **Tessitura TNEW v7** | `POST /api/products/productionseasons` (after a GET for the session cookie) → every production × performance. **No price/genre/auditorium** — pair with the venue site (join on `<prodSeasonId>/<perfId>` in booking links) | National Theatre, Sadler's Wells, Southbank, Almeida, Hampstead, Globe, Old Vic | `_tnew.py` + per-venue enrichment |
| **Savoy Systems** | `*.dll/WhatsOn` embeds `var Events = {…}` JSON (titles, synopses, performances; no price) | Rio, Phoenix, Lexi, Arzner, ActOne | `_savoy.py` |
| **Ticketsolve** | `https://<sub>.ticketsolve.com/shows.xml` (per-performance, `event_category`; prices in per-event XML) | Conway Hall, New Diorama, Jermyn Street, Theatre Peckham, David Lean Cinema | `_ticketsolve.py` (also useful beyond London — UK/IE) |
| **Clusterflick** | Open-source London film aggregator; MIT-licensed repos (incl. the data repos); GitHub release assets several times a day, one asset per venue in `data-transformed` (raw title, venue's film URL, per-performance booking URL + notes, item category); 477 venues. **No prices** | every cinema incl. the hard ones (BFI, Curzon) | `clusterflick` multi-venue whitelist source — **the film source for v1** (see Decisions) |

Spektrix gotchas: always pass a date window (Barbican/Soho time out
otherwise); events include ancillaries (programmes, headsets, "Name a Seat",
staff lunches) — filter on the client's own attribute (`SupplementaryEvent`,
`WebsiteCategorisation`, `Type`…); `webUrl` is usually empty, so
`source_url` = the venue's page (matched by name/id) or the Spektrix booking
URL; `external_id` = instance id is stable. Attribute *names* differ per
client — that's what the per-venue config is for.

## Genre taxonomy

The existing 12 categories fit. London is strongest in **theater** (deepest
subsidised/new-writing scene of any city we run), **film** (repertory density
unmatched), **classical**, and grassroots **pop/rock/alternative**. Notes:

- `flamenco`: drop (no scene).
- `folk`: real — Cecil Sharp House (ceilidhs, balfolk), Green Note, folk
  clubs, plus global/diaspora (Hootananny, Rich Mix).
- `kids`: unusually strong — Unicorn, Little Angel, Polka are kids-only houses.
- **Comedy is the obvious missing category** (Soho Theatre tags it
  structurally, MOTH runs comedy, DICE has `comedy:*`). Out of scope for v1;
  a conversation, not a default.

## Venue index (recommended inclusions)

Slugs are proposals; checked against all 286 registered venues — only
`jamboree` clashes (Barcelona) → `jamboree-london`.

### Theater

| Venue | Source | Category signal |
|---|---|---|
| Royal Court | Spektrix `royalcourt` | all new writing; drop off-site via `TicketVenue2` |
| Young Vic | Spektrix `youngvic` (site is CF; API isn't) | drop `SupplementaryEvent` |
| Bush Theatre | Spektrix `bushtheatre` | `WebsiteCategorisation=Production` |
| Donmar Warehouse | Spektrix `donmarwarehouse` | `Website=Performance` |
| Soho Theatre (+ Walthamstow) | Spektrix `sohotheatre` | `WebsiteFilterCategory1` Theatre/Family (Comedy/Cabaret later; drop Glasgow) |
| Kiln | Spektrix `tricycle` | `WebEventType` Theatre / **Cinema → film** |
| Brixton House | Spektrix `ovalhouse` | `Genre` New Writing / Live Art / Family |
| Arcola, Park, Orange Tree, CPT, The Yard, Southwark Playhouse, Theatre503 | Spektrix | single-genre houses; per-client ancillary filter |
| National Theatre | TNEW + site JSON-LD per performance (auditorium) | drop touring/West End items by location |
| Almeida, Hampstead | TNEW + site prices | all theatre |
| Shakespeare's Globe | TNEW (Queue-it cookie, plain curl OK) | drop tours/exhibition productions |
| New Diorama, Jermyn Street | Ticketsolve | all theatre |
| *Wave 3:* Lyric Hammersmith (noisy; `Type`, drop YPBOC), BAC (`Workstream` + site tags), Stratford East, Coronet, Barbican Theatre | Spektrix | see Barbican note below |

### Dance

| Venue | Source | Signal |
|---|---|---|
| Sadler's Wells (+ Lilian Baylis, Peacock, East) | site alone renders every performance (date, time, "From £", sub-venue); TNEW as cross-check | all dance; sub-venue label (Peacock leans commercial) |
| The Place | Spektrix `theplace` | `WebsiteListing=Performance` (drops classes) |
| Southbank Centre | TNEW + site (cffi) "Performance & dance" label | see Southbank note below |
| Rich Mix | Spektrix `richmix` | `PrimaryCategory` Dance / Performance / Screening |

Dance Umbrella (Oct) is a festival hosted by venues above — annotation, not a venue.

### Kids

Unicorn (Spektrix, all kids), Little Angel (`EventType=In-house show`), Polka
(`Type=Show`, drops workshops), Half Moon (WP HTML, per-performance £) —
plus the family strands of Soho/Lyric/Brixton House via their attributes.

### Classical / opera

| Venue | Source | Signal |
|---|---|---|
| **Wigmore Hall** | own JSON API `/api/v1/listings/whats-on?page=N` (296 items, `pricesText`) | all classical. Probably the single best venue in the city |
| Barbican Hall (+ Milton Court / Guildhall via `GSMDEvent`) | Spektrix `barbicancentre` | `PrimaryArtForm`, `EventType`; drop `SeasonPromoter=Raymond Gubbay` |
| Sinfonia Smith Square (St John's Smith Square) | Spektrix | `Type`, `Series` (Lunchtime Concerts, Baroque festival, Jazz in the Crypt → jazz) |
| St Martin-in-the-Fields | Spektrix | **`SubCategories` drops its own 98-event Candlelight series** structurally; keep Masterworks/Lunchtime/Choral; Crypt Live → jazz |
| Cadogan Hall | Spektrix | `Genre1`/`Genre2`; drop Tribute |
| Royal College of Music | Spektrix | `Category` Concert/Opera (free/PWYC) |
| Royal Academy of Music | Spektrix | all music (free student concerts) |
| Blackheath Halls + Trinity Laban | Spektrix (one client, two orgs) | split by `OrganisationOrVenue`/`Location`; `attribute_Price` is already free text |
| Royal Ballet & Opera | `__REACT_QUERY_DEHYDRATED_STATE__` JSON | tag "Opera and music" → classical, "Ballet and dance" → dance; drop tours/cinema/talks |
| Conway Hall Sunday Concerts | Ticketsolve | `event_category=Sunday Concerts` (since 1887, £14) |
| Southbank Centre | `artform-filter=classical-music` HTML + JSON-LD (cffi) | site's own artform pill |
| LSO St Luke's | lso.co.uk HTML, `?location=lso-st-lukes` | free Friday lunchtimes |
| St James's Piccadilly | WP REST `event-category` | **`free-concerts` + `the-sixteen` only** — drops the tourist Vivaldi-by-candlelight series |
| Kings Place | Spektrix (no genre) + site genre path `/whats-on/{classical,folk,jazz}/` (cffi) | site URL path |
| *Later:* ENO (eno.org production whitelist ⨝ Coliseum Spektrix), Opera Holland Park + Grimeborn (summer), Temple / St Paul's organ recitals | | |

### Folk / global

Cecil Sharp House (Spektrix `efdss`, `TAAArtform` Music/Dance), Green Note
(WP HTML with £), Islington Folk Club (static table), Kings Place folk
(above), Union Chapel + Hootananny (DICE), Rich Mix (Spektrix). Later:
Walthamstow / Cellar Upstairs folk clubs (prose pages).

### Jazz

**No jazzin.amsterdam equivalent exists.** jazzinlondon.net (the 1971 guide)
expired; London Jazz News is news-only; Jazz Near You is Cloudflare-blocked.
**jazzlondonlive.com is a good source** — the London analogue of jazz010: an
editorially compiled gig guide (Jazz London Live Ltd; app, newsletter, paid
"get listed" promos), server HTML, no robots rules, no Cloudflare. `/jazz-dates`
has the current month in one page (728 events across ~85 venues in October:
`DD/MM/YYYY HH:MM`, venue, free-text price, title, link to the venue's own
page); `/venue/YYYY/MM/{id}` gives one venue's month (stable numeric ids). Two
things to design around:

- **Monthly horizon.** It's compiled per month: on 24 Oct only October is
  listed (177 events left), November is empty everywhere. Coverage itself is
  fine (health compares against events the previous run *saw*, and next
  month's events were never seen), but the source's event count shrinks
  towards each month-end, so the event-count rule needs a month-boundary
  allowance, and the agenda will look thin in the last week until the next
  month posts. Fetch next month's pages too, so it's picked up the night it
  appears.
- **Skew.** Strong on mainstream, straight-ahead, supper-club and suburban
  jazz: home-counties clubs (Guildford, Maidenhead, Cambridge, Beckenham…)
  need a denylist, as jazzin.amsterdam has its postcode gate; halls and dinner
  shows (Cadogan, Bechstein, Boisdale, Crazy Coqs) stay off the whitelist.
  Weak on the experimental/new-UK-jazz scene: no Cafe OTO, IKLECTIK or
  Hundred Years Gallery, and only ~4 dates a month for 91 Living Room.

So jazz = a jazzlondonlive whitelist (opt-in, exact venue names — not
opt-out like jazzin) + a few per-venue scrapers:

| Venue | Source |
|---|---|
| Vortex (non-profit, free Sunday jam) | jazzlondonlive; later own day pages (`/events/YYYY-MM-DD/`, prices) |
| Ronnie Scott's | jazzlondonlive (no prices); own site needs cffi |
| PizzaExpress Jazz Club Soho | open JSON API `api.pizzaexpresslive.com` (price in pence) |
| 606 Club, Toulouse Lautrec (jams), Jamboree (free weekly sessions), Jazz Cafe POSK, Jazzlive at the Crypt, Spice of Life (jams), 91 Living Room, Morocco Bound, The Archduke / sYp (free), Bull's Head Barnes | jazzlondonlive whitelist |
| **Cafe OTO** | own site (server HTML, full price ladder; `Crawl-delay: 10`) — **alternative** |
| **Hundred Years Gallery** | own site (single HTML list; filter its own "Music :" / "Residency :" type prefix) — alternative |
| Kings Place jazz, SSS Jazz in the Crypt, St Martin's Crypt Live | via their owning sources above (exclude from jazzlondonlive) |

EFG London Jazz Festival (13–22 Nov) → annotation, not a venue.

### Film — one `clusterflick` whitelist source

| Venue | Clusterflick asset | Direct fallback (if ever needed) |
|---|---|---|
| BFI Southbank | `bfi.org.uk-southbank` | AudienceView, Cloudflare (cffi) |
| Prince Charles Cinema | `princecharlescinema.com` | one HTML page, **prices** |
| The Garden Cinema | `thegardencinema.co.uk` | HTML, some price text |
| Rio, Phoenix, Lexi, Arzner, ActOne | per site | Savoy `var Events` JSON (one parser) |
| The Castle Cinema | `thecastlecinema.com` | HTML, **prices** |
| Close-Up Film Centre | `closeupfilmcentre.com` | embedded JSON |
| ICA | `ica.art` | HTML cards |
| Genesis | `genesiscinema.co.uk` | Admit One HTML |
| The Nickel | `thenickel.co.uk` | `initialScreenings` JSON |
| The Cinema Museum | `cinemamuseum.org.uk` | Tribe JSON-LD, **prices** |
| Curzon Soho, Curzon Bloomsbury (Bertha DocHouse) | `curzon.com-soho`, `curzon.com-bloomsbury` | Vista OCAPI via page token (cffi) |
| *Second wave:* Ciné Lumière, Regent Street Cinema, ArtHouse Crouch End, Horse Hospital, JW3, Picturehouse Ritzy/Hackney | per site | |

Asset names: check the latest `data-transformed` release's asset list when
building. Clusterflick also carries film events at venues another London
source owns (Barbican, Kiln, Rich Mix, Cafe OTO, Cadogan Hall, Conway Hall,
EartH, Bush Theatre, Dalston Superstore) — those stay with their owner and
are **not** on the clusterflick whitelist.

Mapping: one ScrapedEvent per `performances[]` entry; `title` = the venue's
raw `title` (not the TMDB-normalised one), `source_url` = item `url` (the
venue's film page), `external_id` = the performance's `bookingUrl` (stable,
per screening), `notes` ("35mm", "Sing Along", "Q&A", "Part of <season>") and
`format.source` → `annotations`. Keep item categories `movie`,
`multiple-movies`, `shorts`; drop `quiz`, `tv` (and decide on `talk`) — the
source's own labels. Description: the TMDB summary is the only one, so either
leave it empty or use it with TMDB's required attribution. Price: none; the
four venues that publish one (Prince Charles, Castle, Cinema Museum, Garden)
can be moved to direct scrapers later if price matters.

### Club / pop / rock / alternative (DICE)

| Category | Venues (DICE venue name must match exactly) |
|---|---|
| club | Phonox, Colour Factory, FOLD, Village Underground |
| pop | MOTH Club, The Lexington, Oslo Hackney, The Shacklewell Arms, Paper Dress Vintage, Sebright Arms, The Old Blue Last, Islington Assembly Hall |
| rock | The 100 Club, The George Tavern, The Black Heart, Electric Ballroom |
| alternative | EartH, New River Studios |
| folk | Union Chapel, Hootananny Brixton |
| own site, DICE is partial | Windmill Brixton (door-only shows; HTML with £), Dalston Superstore, Rich Mix |

Without genre tags (public pages), a DICE venue's category comes from its
list membership; filter non-music by DICE `type_tags` where the page carries
them (MOTH comedy, Signature Brew quizzes).

## Decisions (with the owner, 2026-10-24)

1. **DICE: venue keys now, a partner key later.** Where a venue embeds the
   DICE widget on its own site (MOTH Club, Strongroom, 91 Living Room…), use
   *that venue's* key, and only to fetch *that venue's* events — exactly what
   its public widget shows. Everywhere else, the public venue page. Record
   the key's origin (the venue page URL) in SOURCE.md; a rotated key shows up
   as a health failure, and the fallback is the public page. Request a DICE
   partner key, then switch every venue to it.
2. **Resident Advisor: skipped.** fabric, Venue MOT, Ormside Projects and The
   Cause are only on RA (`ra.co/graphql`, unofficial; RA's terms forbid
   scraping). Not in v1; the venue ids are kept in
   `docs/london-research/club-gigs.md` in case RA grants access.
3. **Clusterflick: the film source for all curated cinemas.** Checked
   2026-10-24: actively maintained (one maintainer, Alistair Brown; commits
   daily across the pipeline repos, new venues added this week, a
   `data-combined` release several times a day — latest 24 Oct 16:49 UTC).
   Every pipeline repo, including the data repos whose releases we'd read, is
   **MIT**-licensed: use is permitted with attribution (credit Clusterflick in
   SOURCE.md and on the site's about/credits). The showtimes are facts; the
   TMDB summaries are TMDB's (attribution required if shown). Risks: bus
   factor of one, and it's fighting blocks itself (self-hosted runners,
   residential IP rotation) — if it lapses, London film goes dark at once,
   but the health checks would open an issue that night, and every venue
   has a known direct fallback (Film table). A heads-up email to the
   maintainer is good manners, not a blocker.
4. **Borderline curation** — not "too popular"; the question is whether the
   programming is made for locals or is a commercial/tourist product:
   - **Old Vic — in.** Independent non-profit with a great history, but now
     leans on star casting and big-ticket transfers (£100+ tops). Still has
     £10 preview tickets and serious new work.
   - **Ronnie Scott's — in.** The legendary club; main shows are
     tourist-heavy, dinner-table, £40–60+. Its Late Late Show and upstairs
     sessions are where musicians and regulars actually go.
   - **Blue Note London — out for now.** New (2025/26) outpost of the New
     York franchise: big-name bookings at dinner-club prices, no local
     identity yet. Revisit in a year.
   - **E1 — out.** Large Wapping warehouse, mostly external hard-techno party
     brands; little identity of its own.
   - **XOYO — out.** Was a defining residency club; now largely generic
     tech-house nights.
   - **Everyman — out.** Premium sofa-cinema chain, first-run releases.
   - **Picturehouse — later.** Cineworld-owned chain, mostly first-run; the
     Ritzy and Hackney have local identity and some seasons.
5. **Default list: `theater`.**

## Cross-source ownership (one owner per venue)

Venues that appear in several sources and must be owned by exactly one:

- **Barbican** — one Spektrix source owns all categories (classical, theater,
  film, dance). Its `PrimaryArtForm` files dance under Theatre, so dance needs
  the website label or stays under theater for v1.
- **Southbank Centre** — one source (TNEW for performances + site artform
  label for category), covering classical and dance; not two scrapers.
- **Kings Place** — own hybrid source (classical/folk/jazz); exclude from
  jazzlondonlive.
- **Cafe OTO, Green Note, Union Chapel, Wigmore Hall, Cadogan Hall** — appear
  on jazzlondonlive and/or DICE; exclude from those whitelists.
- **Kiln, Rich Mix** — one Spektrix source each, film as a second category.
- **Blackheath Halls / Trinity Laban** — one Spektrix client, split into
  venues by `Location` → a multi-venue source.

## Exclusions (and why)

- **Closed / inactive:** Gate Theatre (closed); Corsica Studios (refurb since
  Mar 2026, recheck 2027); Nambucca, The Borderline (closing); IKLECTIK (lost
  its space, crowdfunding — recheck); Kansas Smitty's, Mau Mau Bar (2020);
  Total Refreshment Centre (licensing closure, domain expired); Matchstick
  Piehouse (no DNS); Oliver's Jazz Bar (domain now a spam blog); Deptford
  Cinema (unverified).
- **Touristic / mainstream:** Fever Candlelight and lookalikes (and the
  in-house candlelight series at St Martin's / St James's, excluded by their
  own labels); Boisdale and supper-club jazz; Raymond Gubbay / tribute nights
  at rental halls; West End commercial houses; multiplexes; rooftop/pop-up
  cinema; O2 Academy, KOKO, Ministry of Sound, megavenues.
- **No usable source:** Royal Albert Hall (Imperva wall for curl *and* cffi;
  Proms are summer-only anyway — browser helper if ever); Church of Sound,
  Steam Down (DICE/Instagram only, irregular); Irish sessions; Bachtrack
  (JS-only, adds nothing over direct sources).
- **Low value:** Goethe-Institut film (~7 screenings), Siobhan Davies (classes),
  Trinity Laban's own site (JS, nothing found; partly covered via Blackheath),
  Rambert (touring, plays at Sadler's), Hackney Empire (no genre labels,
  mostly comedy/tribute), Brilliant Corners / Ridley Road (DJ bars, not jazz).

## Things that differ structurally from our other cities

1. **Scale.** London will out-volume every other city combined: Soho Theatre
   alone has ~1,500 upcoming performances, Prince Charles ~700 showings,
   Spektrix theatres expose 300–2,000 instances each. Before launch, check the
   static build time/page weight of a London list page and the Today page; a
   per-source horizon cap (e.g. 8 weeks) may be needed for long theatre runs.
2. **One-row-per-performance is native here.** Spektrix/TNEW/Ticketsolve all
   give real per-performance rows — no expansion logic needed. Only
   Finborough (date range + weekly times) doesn't; skip it for v1.
3. **English only** — the first single-locale city. Check the locale switcher
   and `/:city/:locale` routing behave with `locales: ["en"]`.
4. **GBP.** New `price.py` helpers: `format_gbp` → `"£12"` (UK convention:
   symbol first, unlike `"12€"`), ranges with the same 2× rule, `gbp_amounts`
   from free text ("£10 / £8 conc", "£9 - 22 advance", "Free"); Spektrix and
   DICE give pence/decimal amounts.
5. **Geocode radius.** `geocode.CITY_CENTRES["london"]` (51.5074, −0.1278,
   "gb"); 35 km covers Greater London (Polka/Wimbledon, ActOne/Acton,
   Blackheath all inside).

## Build plan

0. City config: `seed.CITIES += ("london", "London")`; `web/src/lib/cities.ts`
   (`locales: ["en"]`, `defaultLocale: "en"`, `defaultList: "theater"`,
   `timezone: "Europe/London"`, `center: [-0.1278, 51.5074]`); `CITY_CENTRES`;
   GBP price helpers.
1. **`_spektrix.py`** + ~25 venues (theatre wave 1, The Place, kids houses,
   Barbican, SSS, St Martin's, Cadogan, RCM, RAM, Blackheath, Cecil Sharp
   House). The biggest lever — one parser, per-venue attribute config.
2. **`_dice.py`** (venue's own widget key, else public venue page) + ~20
   gig/club venues.
3. Film: **`clusterflick`** whitelist source (~17 cinemas, decision 3).
4. Jazz: **jazzlondonlive** whitelist (denylist out-of-London, halls, dinner
   clubs; health rule tolerant of the month boundary) + Cafe OTO, Hundred
   Years Gallery, PizzaExpress.
5. **`_tnew.py`** + Sadler's Wells, National Theatre, Southbank, Almeida,
   Hampstead, Globe.
6. Direct classical/folk: Wigmore Hall, Royal Ballet & Opera, LSO St Luke's,
   St James's Piccadilly, Kings Place, Green Note, Islington Folk Club;
   **`_ticketsolve.py`** (Conway Hall, New Diorama, Jermyn Street).
7. Later: wave-3 theatres, second-wave cinemas, direct film scrapers where
   price matters, Windmill/Dalston Superstore own sites, ENO, summer opera.

## Where I'd start

If only ten venues: **Wigmore Hall** (classical), **Royal Court** and **Young
Vic** (theater), **Sadler's Wells** and **The Place** (dance), **Prince
Charles** and **Close-Up** (film), **Cafe OTO** and **Vortex** (jazz /
alternative), **MOTH Club** (pop) — plus **Cecil Sharp House**, whose
ceilidhs and balfolk are the most solo-go-er-friendly thing in the city (drop
in, get taught, dance with strangers). But the efficient first PR is batch 1:
the Spektrix helper turns ~25 of the best venues in London into config.

Confidence: platform findings are verified (live API responses, counts as of
2026-10-24). Venue fit is desk research, not fieldwork; small entries
(Morocco Bound, Rye Wax, folk clubs) rest on one or two sources. Several
sites timed out on HTTPS from the research machine but answered on HTTP
(Hundred Years Gallery, Total Refreshment Centre) — re-probe from prod. Raw
per-genre research notes: `docs/london-research/{film,jazz,classical,theatre,club-gigs}.md`
(written before the decisions above; where they disagree, this file wins).
