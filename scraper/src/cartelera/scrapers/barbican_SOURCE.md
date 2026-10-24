# Barbican — source map

Source slug: `barbican` (London), multi-venue. One Spektrix client,
`barbicancentre`, on the custom host `https://spektrix.barbican.org.uk`
(`/barbicancentre/api/v3`), sells the Barbican Centre and the neighbouring
buildings its box office handles:

| Venue slug | Building | Client venues (rooms, via seating plan → `/venues`) |
|---|---|---|
| `barbican` | Barbican Centre, Silk Street EC2Y 8DS | Barbican Hall, Barbican Theatre, The Pit, Cinema 1/2/3, Frobisher Auditorium 1, Fountain Room, Barbican Art Gallery, Conservatory, Club Stage Level -1, Barbican Foyers |
| `milton-court` | Milton Court (Guildhall School), 1 Milton Street EC2Y 9BH | Milton Court Concert Hall / Theatre / Studio, Rehearsal Room 3 Milton Court |
| `guildhall-school-silk-street` | Guildhall School main building, Silk Street EC2Y 8DT | Silk Street Theatre (+ Unreserved), Silk St Music Hall, Guildhall School (Lecture Recital Room) |
| `lso-st-lukes` | LSO St Luke's, 161 Old Street EC1V 9NG | LSO St Luke's |

Dropped rooms: St Giles Cripplegate and Temple Church (off-site churches; a
handful of Barbican Presents / BBC Singers concerts), Great Hall Guildhall
(staff lunches), Explore Barbican Tours, CarParks, Barbican Merchandise,
Add Ons, Frobisher Rooms (Darbar workshops), the "Unknown" venue, and the
**Wildcard** plan (every LSO concert has a twin instance on it,
`attribute_InstanceType = "wildcard"`). Instances with `InstanceType`
`wildcard` or `streaming` (online ticket) are dropped wherever they sit.

Data and pipeline: the shared `_spektrix.py` pieces (see
`spektrix_SOURCE.md`) — fetch_programme, fetch_plan_venues, select, build —
composed in `BarbicanScraper.scrape`, because two things don't fit
`spk.scrape`: the paginated site join and a price-band filter.

**Always send the date window**: unfiltered `/events` hangs. Six months =
~380 events / ~4,700 instances; `/instances` takes ~40 s (3,355 of the rows
are the Robert Ryman exhibition's timed entries). A run is ~75 s.

## Curation (event attributes — never titles)

Event-level exclusions first: `SuppEvent`, `BasketAddOn` or `MembersOnly`
true (champagne treats, food add-ons, touch tours, members' screenings);
`SeasonPromoter` = **Raymond Gubbay** (commercial candlelit/film-music
concerts at the Hall). Then by `PrimaryArtForm` + `EventType`:

| PrimaryArtForm | Kept EventType → category | Dropped |
|---|---|---|
| Classical Music | Orchestral, Chamber, Recital, Choral, Opera and Oratorio, Concert, Film and live music, Multi-media Performance, Big Band → **classical** | Talk, Workshop, Screening - Film (Darbar film), *empty* (a keynote lecture; the two empty-type concerts sit in off-site rooms anyway) |
| Cinema | Screening - Film, Talk + Screening, Relaxed Screening, Screening + Workshop, Concert + Film Screening + Talk → **film**, *and only if published on barbican.org.uk* (below) | Talk, *empty* (Screen FYC London — industry awards screenings; The General silent-film event) |
| Theatre | *empty* (the Barbican's own theatre & dance seasons carry none), Play - Classical, Play - Modern, Immersive, Performance, Multi-media Performance → **theater** | Touch Tour |
| any other (Contemporary Music, Art Gallery, Creative Collaboration…) with EventType Concert / Big Band | by `EventGenre`: Jazz → **jazz**, Pop → **pop**, Alternative and Indie → **alternative**, Western Folk Music → **folk** | every other genre (Electronica, Americana and Country, South Asian, Middle East…, Hip Hop, Reggae, R&B, Experimental, Poetry, Contemporary Classical) — no clean Cartelita category |
| Other, Art Gallery (exhibitions/tours/talks), Creative Collaboration (workshops/clubnight), "" | — | staff Christmas lunches, tours, Conservatory visits, yoga, parking, test events ("BEN PRICING REPORTING", "HH BASKET TESTING", "MULTIPLE PLANS") |

- **Dance**: filed under PrimaryArtForm Theatre (Boy Blue, Tout/Rien,
  Absence and Presence…) with no EventType/EventGenre to split it (the one
  "Contemporary Dance" genre is a Young Barbican workshop). The website only
  says "Theatre & dance" (listing tag, dataLayer `primary_artform`, page
  brand class). So dance stays **theater** for now.
- **Jazz/pop/alternative/folk** come only from `EventGenre` on music events
  outside Classical Music. Classical-filed events with a Jazz/Pop/Hip Hop
  genre (Guildhall Big Band, DJ Shadow & BBC SO, the Eleanor Rigby
  Experience) stay classical: the client's primary label wins. Americana and
  Country (Punch Brothers, The Delines) and Electronica (Robert Henke, Jlin…)
  are left out on purpose.
- **Cinema needs the site**: the box office holds unpublished test
  screenings ("Georgia's Test Screen") in Cinemas 1–2 with exactly a real
  film's attributes. A film is kept only when a barbican.org.uk show page
  carries its id (`curate(pages)`). Side effect: a screening the site hasn't
  published yet (a preview, some relaxed screenings — their pages answer
  403) appears once it is published.
- `TargetAge` = Children and Family (family films, LSO Discovery concerts,
  Univers) would support a `kids` category; not taken yet.

## Fields

| Field | Source |
|---|---|
| `title` | the show page's dataLayer `title` when every Spektrix event on that page shares one name ("London Symphony Orchestra/Sir Antonio Pappano", "NAZA" rather than "NAZA (15)"); else the box-office `name` |
| `start_date`/`start_time` | instance `start` |
| `external_id` | instance `id` |
| `source_url` | barbican.org.uk show page (site join); else the Spektrix event page `https://spektrix.barbican.org.uk/barbicancentre/website/EventDetails.aspx?EventId=<n>` (LSO St Luke's chamber series, rentals the Barbican doesn't list) |
| `price` | price list band defaults **minus band "Y"** → `spk.price_text` (2x rule). Band Y is the Young Barbican allocation (16–29 scheme, sold as ticket type "Standard"; every checked show page says "Young Barbican £12"/"£10"/"£18" = its band-Y amount). Prices exclude the Barbican's transaction fee (£1.50 cinema, £4 Hall/Theatre) like the site's "(£25 + £4 transaction fee)". |
| `description` | the box office has none for programme events (373/377 `htmlDescription` are an empty div); taken from the show page: dataLayer `subtitle` + `og:description` |
| `image_url` | show page `og:image` (box office `imageUrl` is empty) |
| `annotations` | instance access flags (AudioDescribed, Captioned, Relaxed). Barbican's BSL flag is `attribute_BSL`, which the helper's ACCESS_FLAGS (`BSLInterpreted`) doesn't know — none were true on 2026-10-24 |
| `venue_slug` | plan → room → building (table above) |

## The site join (barbican.org.uk)

- Listing: `/whats-on?dates[min]=<today>&dates[max]=<+183d>&af[6]=6&af[11]=11&af[16]=16&af[21]=21`
  (the site's art-form facets: classical, contemporary music, cinema,
  theatre & dance), **paginated** `&page=0,1,…` — 30 cards a page, ~16
  pages; a long run repeats on many pages (Hamlet ×70), so paging stops at
  the first page with no cards (cap 40). Cards: `a.search-listing__link`.
- Each show page (~290) carries
  `var dataLayer = [{"title", "subtitle", "eventInfo": [{"name", "id"}]}]`
  with **full Spektrix event ids**. A page may sell several events (an LSO
  concert's paired events, both named "London Symphony Orchestra"); an
  event on several pages goes to the page selling the fewest. Plain httpx,
  no Cloudflare; ~10 s at 4 concurrent requests.
- Not on the site: LSO St Luke's (lso.co.uk sells its own series), some
  rentals at Milton Court (English Schools' Orchestra, Fidelio Orchestra),
  Guildhall Big Band. These link to the Spektrix event page.

## Ownership notes

- **LSO St Luke's**: `docs/london.md` also plans a direct lso.co.uk source
  for it (free Friday lunchtimes, BBC R3 lunchtimes — not in this feed).
  This source owns `lso-st-lukes` now; whichever source keeps it, the other
  must drop it.
- Guildhall School / Milton Court: GSMD's own site is JS-only; this feed is
  the only source for their public shows.

## Verification

Last verified **2026-10-24**, live run: **516 performances / 250 events**
(barbican 448, milton-court 36, lso-st-lukes 20, guildhall-school-silk-street
12; theater 196, film 149, classical 148, jazz 15, alternative 5, pop 2,
folk 1). Priced 100%, site URL 96%, description/image 96%.

HTTP cross-check against the show pages (independent BeautifulSoup read):

| Show | Scraper | barbican.org.uk |
|---|---|---|
| Jaga Jazzist | 2026-11-19 19:30, milton-court, £35 (bands 25–35) | "Thu 19 Nov 2026, 19:30, Milton Court", "From £29 (£25 + £4 fee)", "Young Barbican £12" |
| Squid + Factory Floor | 2026-12-05 20:00, barbican, £27.50 | "Sat 5 Dec 2026, 20:00, Hall", "From £26.50 (£22.50 + £4)" |
| LSO/Sir Simon Rattle | 2027-01-07 19:00, barbican, £18–75 | "Thu 7 — Sun 10 Jan 2027, Hall", "From £22 (£18 + £4)" |
| John Coltrane…: Mo' Better Blues | 2026-11-15 14:00, barbican, £14 | "Sun 15 Nov 2026, 14:00, Cinema 3", "£15.50 (£14 + £1.50)" |
| Howl's Moving Castle (FFW) | 2026-10-25 13:15, £2.50–5 | "Under 18s £2.50, 18 and over £5" |
| Tiger Country | 2026-10-24 14:00, milton-court, £15 | "Milton Court Studio Theatre", "Admission £15" |
| Univers | The Pit, £14 | "The Pit", "Adult ticket £14" |
| Hamlet Hail to the Thief | 2026-10-31 19:45, barbican, £25–105 | "Barbican Theatre", "From £34 (including a £4 fee)" — the run has 7 price lists; the box office's cheapest standard band in this one is £25 (G) |

Cold-start (`migrate && seed && run barbican` on a scratch DB): 516 rows ==
516 scraped performances (no occurrences collapsed). Categories per venue as
above. 515 of 516 priced: the DJ Shadow & BBC SO price list answered 404
(off sale) on every instance tried in that run.
