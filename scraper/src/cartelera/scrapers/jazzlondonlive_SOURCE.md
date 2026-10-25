# jazzlondonlive.com — source map

Multi-venue **whitelist** source (`jazzlondonlive`) for London jazz (city
`london`, category `jazz`). jazzlondonlive.com (Jazz London Live Ltd, Sarah
Chaplin; app + newsletter, paid "get listed" promos) is a hand-compiled
monthly gig guide: ~730 gigs across ~80 venues in October 2026. Server HTML,
no JSON, no Cloudflare; robots.txt is a 404 (no rules). Client: plain `httpx`
with `CARTELITA_COMPAT_UA`, ≤3 concurrent requests.

Opt-in, **exact venue-name matching** (like jazz010 — *not* opt-out/discovery
like jazzin.amsterdam): only names in `ALIASES` are emitted; names in
`EXCLUDED` are skipped quietly; any other name is logged as
`venues not in the whitelist (review)` so a new venue gets an editorial look.

**Owner TODO:** like jazz010, this is one person's labour; consider telling
the editor (info@jazzlondonlive.com) that Cartelita reads the guide nightly
and links out to every venue's own page.

## Pages

| URL | What | Used for |
|---|---|---|
| `/jazz-dates` | the **current** month, every venue, one page | current month's rows |
| `/events_by_month/YYYY/M` | that month's venue index: cards `div.article a[href=/venue/YYYY/MM/{id}]` + `p.title` venue name; empty until the month is posted | venue page ids (fallback links); next month's venues |
| `/venue/YYYY/MM/{id}` | one venue's month (h1 = venue name) | next month's rows, once posted |

`/jazz-dates` takes no month parameter (`?month=`, `/jazz-dates/2026/11` →
ignored / 404), so next month comes from the per-venue pages. A run fetches:
`/jazz-dates` + current and next month index (3 requests), plus one page per
whitelisted venue for a month that isn't on `/jazz-dates` (0 until the
editor posts next month, then ~36). If `/jazz-dates` still shows the previous
month on the 1st, the current month is read through venue pages instead (the
"covered months" check works from the rows' own dates).

## Fields

`/jazz-dates` row = `<h3><span class="text-white">DD/MM/YYYY HH:MM\n{venue}\n{price}</span><a href="{link}"><span>{title}</span></a><span class="text-888B8D">{note}</span></h3>`
(three lines in the span; price line absent when unknown). A venue page row
is the same without the venue line (`DD/MM/YYYY HH:MM {price}`), the note in
a following `p.text-888B8D` — **but the venue page folds the note into the
title**: "The GAB Trio (Live Show)" vs "The GAB Trio" + note "Live Show" on
`/jazz-dates`. Titles therefore change when a month moves from venue pages
(next month) to `/jazz-dates` (current month); the key below doesn't use
the title, so the upsert just updates it.

| Field | Source |
|---|---|
| `start_date`/`start_time` | `DD/MM/YYYY HH:MM` (always both) |
| venue | the venue line (or the venue page's index name), exact match against `ALIASES` |
| `title` | link text |
| `price` | free text → `parse_price`: £ amounts via `price.gbp_amounts`; a `/`/`,` tier list ("£13 / 10 / 5", "£20 Advance / 23 Door", "£19.25, 26.25") → the highest (others are concession/advance tiers); a dash range ("£9 - 22 advance") → `format_gbp_range` (2x rule); "Free", "free", "Free/donations" → `free`; no £ amount ("From 15") or empty → `None` |
| `source_url` | the row's link when it is a real `http(s)://host.tld…` URL (the venue's own event/booking page — often a generic listing page like `vortexjazz.co.uk/events/`); junk links (`http://`, ~7/month, e.g. Clocktower Cafe) → the guide's venue page `/venue/YYYY/MM/{id}` |
| `annotations` | the editor's note when ≤3 words ("Live Show", "Jam Session", "Big Band concert") |
| `description` | the note when longer ("Modern jazz/soul/crossover vocal performances; 4 sets") |
| `external_id` | `YYYY-MM-DDTHHMM@{link}` (or `YYYY-MM-DDTHHMM` for junk links). There's no per-event id; links are shared by a residency's nights (Ronnie's "mingus-bb" ×12) and by every gig of venues that link a generic page, and titles differ between the two page types — so date+time+link. Two different gigs on one key at one venue get `#{title}` appended. |
| `language`, `image_url` | not available → `None` |

Rows before today (Europe/London) are dropped.

## Health: the monthly horizon (follow-up, not handled in code)

The guide is compiled **per month**; on 24 Oct only October was posted
(November index and venue pages empty). So the source's event count shrinks
every day towards month-end (99 upcoming events on 24 Oct, down from ~700 on
the 1st) and jumps back when next month is posted. Coverage is unaffected
(health compares against events the previous run saw), but an event-count
rule will see the decline as a drop each month. **Follow-up for the health
owner:** a month-boundary allowance for this source (don't change health code
from here). The agenda will also look thin in the last days of a month until
the editor posts the next one.

## Venue whitelist (London, jazz)

Curation test: clubs, pubs and bars with a real, recurring jazz programme for
locals, inside Greater London. Addresses from the guide's own `/jazz-venues`.

| slug | guide name | note |
|---|---|---|
| `606-club` | 606 Club, Chelsea | musicians' club since 1976 (non-members dine) |
| `ronnie-scotts` | Ronnie Scott's, Soho | main room + Late Late Show / Upstairs; the guide has no prices |
| `vortex-jazz-club` | Vortex Jazz Club, Dalston | non-profit club |
| `toulouse-lautrec` | Toulouse Lautrec, Kennington | club + jam sessions |
| `jamboree-london` | Jamboree, WC1 | free weekly sessions (`jamboree` is Barcelona's) |
| `jazz-cafe-posk` | Jazz Cafe POSK, Hammersmith | Polish centre club |
| `jazzlive-at-the-crypt` | Jazzlive at the Crypt, Camberwell | volunteer Friday club |
| `spice-of-life` | Spice of Life, Soho | jams (the guide lists only its jazz nights) |
| `morocco-bound-wandsworth` | Morocco Bound Bookshop, SW18 | bookshop-bar |
| `morocco-bound-bermondsey` | Morocco Bound, SE1 | bookshop-bar |
| `the-archduke` | The Archduke, Waterloo | free nightly jazz bar |
| `syp` | sYp, EC3 | free jazz bar |
| `fox-and-firkin` | Fox & Firkin, SE13 | pub, jazz + jams |
| `east-side-jazz-club` | East Side Jazz Club, Leytonstone | weekly club |
| `clapham-common-jazz-club` | Clapham Common Jazz Club @ Omnibus Theatre | monthly club |
| `bulls-head-barnes` | Bull's Head, Barnes | historic jazz pub |
| `karamel-club` | Karamel Club, Wood Green | community arts club, ~12/month |
| `the-woodman-highgate` | The Woodman, Highgate | free Wednesday jazz |
| `duke-of-hamilton-hampstead` | Duke of Hamilton, Hampstead | Hampstead Jazz Club |
| `george-iv-chiswick` | George IV, Chiswick | weekly "Jazz at George IV" |
| `bull-and-gate` | Bull & Gate, Kentish Town | Monday jazz |
| `club-langley` | Club Langley, Beckenham | Spike's Place weekly club (LB Bromley) |
| `oval-tavern-croydon` | Oval Tavern, Croydon | free Sunday jazz |
| `clocktower-cafe-croydon` | Clocktower Cafe, Croydon | weekly lunchtime jazz |
| `jazz-train-shoreditch` | Jazz Train, Shoreditch | free Sunday jazz at Rolling Stock |
| `the-mildmay-club` | The Mildmay Club | weekly Friday jazz (social club) |
| `eltham-jazz-club` | Eltham Jazz Club, SE9 | monthly club |
| `ziggys-world-jazz-club` | Ziggy's World Jazz Club, N21 | club at The King's Head |
| `b3-lounge` | B3 Lounge, N12 | jazz nights at The Bohemia |
| `milford-arms-isleworth` | Milford Arms, Isleworth | fortnightly pub jazz |
| `lauderdale-house` | Lauderdale House, Highgate | "Jazz in the House" series |
| `the-washington-hampstead` | The Washington, NW3 | pub jazz night |
| `clissold-arms` | Clissold Arms N2 | "Jazz Wednesdays" |
| `springfield-bowls-club` | Springfield Bowls & Social Club | fortnightly jam (Acton) |
| `the-turks-head-twickenham` | The Turk's Head, Twickenham | pub jazz |
| `the-southgate-club` | The Southgate Club | "Jazz at Obie's" series |

## Exclusions (names in `EXCLUDED`, reasons)

- **Owned by another source:** PizzaExpress Jazz Club, Soho and PizzaExpress
  Live, Holborn (`pizzaexpress-live`); 91 Living Room (`dice-london`); Green
  Note, Kings Place, Wigmore Hall (classical batch); Cadogan Hall
  (`cadogan-hall`); EartH Theatre (`earth-hackney`); Hootananny Brixton
  (`hootananny-brixton`).
- **Owner decision:** Blue Note London (out for now).
- **Halls / big rooms:** Bechstein Hall, Royal Albert Hall, O2 Academy
  Islington; Jazz Cafe, Camden (a club/soul venue whose jazz-labelled dates
  only appear here — belongs with a club source if anywhere).
- **Dinner / supper-club shows:** Boisdale of Belgravia, Boisdale of Canary
  Wharf (£79 dinner shows), Crazy Coqs, The Pheasantry, Googlies Jazz Supper
  Club, Soul Mama Islington (restaurant shows, £28–68).
- **One-off listings at venues without a jazz programme:** Cafe Yukari,
  Grand Junction, Orange Box, The Cockpit, The Courtyard Sun St Hotel, Weston
  Hall (UWL students' union), World Heart Beat, Sundridge Park Working Mens
  Club.
- **Outside Greater London:** Dawkes Music (Maidenhead), Guildford Pavilion,
  The Guildford Institute, The Stoke (Guildford), Hidden Rooms (Cambridge),
  Marigolds (Harlow), Park Inn Hotel and The Jazz Centre UK (Southend), South
  Hill Park (Bracknell), Splashpoint (Eastbourne), The Bardswell Club
  (Brentwood), The Bear Club (Luton), The Harlington (Fleet), Watermill
  (Dorking).

## Verification

Last verified: **2026-10-24 via HTTP cross-check.** Live scrape: 99 upcoming
events (24–31 Oct; November not posted yet) at 26 whitelisted venues
(Ronnie's 34, Vortex 11, 606 9, Jamboree 6, …). Price 62/99 (Ronnie's 34
have none on the guide; 15 free); start_time 99/99; 2 junk links fell back
to the guide page. Independent check: regex-parsed a fresh `/jazz-dates`
(not the scraper's code) for whitelisted rows from today → the same 99
(venue, date, time, title) keys, prices agreeing. Venue sites: Vortex's own
day page `/events/2026-10-26/` — KOPER8, music 20:30, "Standard £17.50" ==
ours (20:30, £17.50); B3 Lounge's shop page — Dave Lewis Quartet 25/10/2026
19:00, £12.00 == ours. (Toulouse Lautrec's event page renders its details
client-side; not used.)
