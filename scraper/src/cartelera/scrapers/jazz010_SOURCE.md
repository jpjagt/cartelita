# jazz010.live — source map

Multi-venue **whitelist** source (`jazz010`) for Rotterdam jazz (city
`rotterdam`, category `jazz`). jazz010.live ("De Rotterdamse Jazzagenda",
Boplicity Software; jazzinrotterdam.nl redirects here) is a hand-curated
agenda, server-rendered HTML, no JSON API we may use. Client: plain `httpx`
with the honest UA `Cartelita (+https://cartelita.co)` — no bot
protection.

**Owner TODO:** jazz010 is one person's labour of love (like jazzin.amsterdam's
maintainer). Consider emailing the author (contact form at
https://jazz010.live/contact, or via https://boplicity.nl) to say Cartelita
reads the agenda nightly, links back to every event page, and ask whether
they mind / prefer a feed.

## robots.txt (checked 2026-10-14)

Disallows AI crawlers (ClaudeBot, GPTBot, …) entirely, and for `*`:
`/api/`, `/add-to-calendar/`, `/contact/`, `/thanks`, `/crawler-info`,
`/venue`, `/redirect`. Note `Disallow: /venue` is a prefix rule, so it also
covers the `/venues` index — **the scraper never fetches `/venue*`**; the
venue table below is maintained by hand from the event pages. We fetch only
`/events?start=YYYY-MM-DD` and `/event/<slug>` (allowed), one list page at a
time and at most 3 detail pages concurrently (~35 list + ~85 detail requests
per run).

## List: `/events?start=YYYY-MM-DD`

(`/events` without `start` redirects to the homepage.) Each page covers 14
days from `start` (inclusive); `section.listing-footer a` ("VOLGENDE") links
`start+14`. The boundary day appears on both pages → dedup on external_id.
VOLGENDE exists forever (empty pages far into the future), so we start at
today (Europe/Amsterdam) and stop after **6 consecutive empty pages**
(cap 40 pages). Events run ~10-13 months ahead (Vrijmoed books a year out).

Per `article.listing` in the main list (the `section.regional` "IN DE
BUURT" block — Den Haag, Dordrecht — is skipped structurally):

| Field | Source |
|---|---|
| `start_date`/`start_time` | `.timestamp` `"wo 14 oktober 19:30"` (Dutch month; time sometimes absent → `None`). No year: first (day, month) on/after the page's `start`. |
| venue | `.venue` text = the **location** (e.g. `Nivon`, `Hillegondakerk`), matched case/whitespace-insensitively against `ALIASES` |
| `title` | `.artist a` text |
| slug | `.artist a[href]` = `/event/<slug>` |
| `price` flags | `.free-entrance` "GRATIS" → `free`; `.sold-out` "UITVERKOCHT" → `sold-out` (both override the detail price) |
| `annotations` | `.tip` "TIP!" (editor's pick) → `"tip"` |

## Detail: `/event/<slug>`

| Field | Source |
|---|---|
| `price` | `a.button` "TICKETS - € 7,50" / "TICKETS - € 45,--" → `7,50€` / `45€`; "TICKETS -" (no amount) or no button → `None` (tickets not on sale yet; ~40% of events, mostly Vrijmoed's far-future dates) |
| `description` | `.event-description` paragraphs + `.event-lineup` ("Bezetting: Name (instrument), …") |
| `image_url` | `img.event-photo[src]` (jpeg fallback, absolute) |
| `annotations` | `.event-header` = the organiser/series (e.g. "Cross Over Hillegonda", "Jazz in Crooswijk"), added when it differs from the venue |
| — | `.venue-address` "Adres: street - city" or "Locatie: name"; `.event-footer` BRON link to the venue's page — used for building the venue table, not per event |

- `source_url` = `https://jazz010.live/event/<slug>`.
- `external_id` = `<slug>@<YYYY-MM-DD>T<HHMM|none>`. The slug embeds a date
  but it is **not** trustworthy (copied entries keep a stale date, e.g.
  `hotspot-hutspot-…-2026-09-18` listed on 30 Oct, `jazzland-…-invalid-datetime`),
  so the listing's own date/time qualifies it.
- Listings with an empty link (`href="/event/"`, seen once: RAUWFEST at BIRD)
  are skipped with a warning.
- `language`: never stated → `None`. Category: always `jazz` (the whole
  agenda is jazz; there is no finer discriminator).

## Venue whitelist (Rotterdam, jazz)

| slug | jazz010 name(s) | address | note |
|---|---|---|---|
| `vrijmoed` | Vrijmoed | Ketelaarstraat 7 | jazz club, ~4 gigs/week |
| `dizzy` | Dizzy | 's-Gravendijkwal 127 | Rotterdam's classic jazz café |
| `batavierhuis` | Batavierhuis | Pieter de Hoochweg 108 | Global Music Nights / World Sessions |
| `de-fruitvis` | Jazz In De Fruitvis, De Fruitvis | Marconistraat 43 | "Jazz in de Fruitvis" concert series |
| `grounds` | Grounds | Pieter de Hoochweg 125 | world/jazz podium (Codarts orbit) |
| `heerenhuys` | Heerenhuys | Baden Powellaan 12 | Het Park; Sunday concerts |
| `de-machinist` | De Machinist | Willem Buytewechstraat 45 | Delfshaven music venue |
| `het-witte-paard` | Het Witte Paard | Groenezoom 245 | monthly "Jazzzondag" series |
| `hillegondakerk` | Hillegondakerk | — | "Cross Over Hillegonda" concert series (Hillegersberg) |
| `jazz-in-crooswijk` | Nivon | — | "Jazz in Crooswijk" series at the Nivon house |

Addresses unknown to jazz010 (location-only events) are left `None` rather
than guessed. Venue names not in `ALIASES` and not in `EXCLUDED` are logged
as a warning (`venues not in the whitelist (review)`) — that's how a new
venue on jazz010 gets noticed; add it here deliberately.

## Exclusions (reasons)

- **Owned by another source** (docs/nl-cities-plan.md): LantarenVenster /
  "LantarenVenster Rotterdam" (lantarenvenster), de Doelen and "de Studio's"
  (Doelen's own studios, organiser de Doelen → doelen), Annabel, BIRD, Rotown
  (batch 3), plus the rest of the plan's owned list pre-emptively.
- **Outside Rotterdam:** Jazzland Café (Groeneweg 51, Bergschenhoek),
  Westvestkerk (Stichting Gillespie, Schiedam), Jazzpodium Hotspothutspot
  (Kloosterplaats 6, Schiedam), Vulcaan Vlaardingen; the whole regional
  block (Den Haag, Dordrecht).
- **Curation (low signal / not a jazz programme):**
  - Café LaBru — weekly free "Live Jazz" café night, no line-up, no description.
  - Wilskracht Bar & Keuken — restaurant gigs by Stichting Concert Dichtbij
    (blues/tango bands, free), not a jazz spot.
  - De Buurvrouw — monthly open amateur jam session in a neighbourhood
    centre (and the listing's date is inconsistent with its own text).
  - Koffie & Ambacht — coffee bar with a single one-off gig a year out.
  - De Zolder — appears only as a RAUWFEST festival location (no address);
    the festival's other locations (Rotown, BIRD) are owned elsewhere.
  - Not yet seen with events (on jazz010's podia index, no listings now):
    CLUB Cafe, Café Dox, Codarts, De Gele Kanarie, Matrix, Koda, Tante Nino,
    Van Cappellenhuis, Vessel 11, Vroesenpaviljoen, Stadsbrouwerij De Pelgrim,
    … — left out until they list gigs; the review warning will surface them.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live scrape: 85 events,
2026-10-14 → 2027-08-29, 10 venues (Vrijmoed 57, Batavierhuis 7, Dizzy 6,
De Fruitvis 6, Grounds 2, Het Witte Paard 2, Jazz in Crooswijk 2, Heerenhuys,
De Machinist, Hillegondakerk 1 each). Coverage: start_time 84/85 (one
listing has no time), price 50/85 (the rest have no ticket price on jazz010
yet), description 75/85, image 62/85. Independent check: regex-parsed the
fresh first list page (not the scraper's code) → all 18 whitelisted rows
agree on title/date/time/GRATIS; regex-grepped 8 detail pages' "TICKETS - €"
button → all 8 prices agree.
