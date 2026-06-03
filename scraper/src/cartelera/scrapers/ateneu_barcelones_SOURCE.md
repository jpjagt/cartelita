# Ateneu Barcelonès — source map

**Venue slug:** `ateneu-barcelones`
**last verified: 2026-06-02**

## Domain note (important)

The old site `https://www.ateneubarcelones.cat/` has migrated. That host's HTTPS
(:443) is unresponsive and `/agenda` 301-redirects to the homepage. The live site
is now `https://ateneubcn.cat/`, and the agenda lives at:

- **List URL:** `https://ateneubcn.cat/programacio/`  (nav label "Agenda")

`site_url` in the VenueDefinition is kept as the canonical
`https://www.ateneubarcelones.cat` per the project brief, but the scraper fetches
`ateneubcn.cat`.

## Data source

The `/programacio/` page server-renders a `.activitat` card per **upcoming**
activity (currently a ~2-week window). Each card carries everything we need:

| field         | location                                                        |
|---------------|-----------------------------------------------------------------|
| title         | `h4.title`                                                      |
| detail URL    | `a.link[href]`                                                  |
| date          | a class token on `.activitat` like `2026-06-10` (ISO)           |
| time          | a class token on `.activitat` like `18:30:00` (HH:MM:SS, local) |
| activity type | `p.tipus` text (also `tipus-<id>` class) — the discriminator    |
| section       | `p.e-chip` text (also `seccio-<id>` class), e.g. "Música"       |
| image         | `.wrap-img img[src]`                                            |
| location      | `p.location span`                                               |

Note: there is also an `admin-ajax.php?action=get_activities_filter` endpoint
(nonce in page) that returns the FULL archive (~1130 activities, structured JSON
incl. `campos_activitat_tipus` / `campos_activitat_data_inici`). The site's
filtering is purely **client-side** — that endpoint always returns everything and
the rendered page is the future window. We parse the rendered cards (one HTTP
request, no nonce) because they already carry every future event; the AJAX dump is
mostly a past-events backlog (max future date == max rendered date == 2026-06-17
as verified).

## Category mapping (concerts only)

The Ateneu agenda is BROAD: ~95% is talks/tertúlies/book launches/round tables
that are NOT music. We emit ONLY classical-music concerts and DROP everything else.

- **Discriminator:** card has the `tipus-11` class **and** `p.tipus` text
  `"Concerts"` (the venue's own activity-type filter). Equivalent section signal:
  `seccio-9536` / `p.e-chip` == "Música".
- Concerts → `category_slugs = ["classical"]`. The Ateneu's concerts are intimate
  classical chamber recitals/soloists (e.g. the Quartet Vivancos), so `classical`
  is correct; there is no jazz/club programming here.
- The section/cicle label ("Música", a cicle name) → `annotations`, never a
  category.
- All non-`Concerts` activity types are dropped (not force-categorized).

## Price

NOT on the list card; lives on the detail page. The scraper fetches each concert's
detail page (few of them) and reads `p.price.nosocis` ("No socis — 20€") for the
public price → `"20€"`. Member price (`p.price.socis`, usually "Gratuït") is
skipped per the price convention. Catalan free phrases ("gratuït", "entrada
lliure") normalize to `"free"`; "exhaurid…/esgotad…" → `"sold-out"`. Price is
`None` if the block is absent.

## external_id

Slug from the detail URL, qualified by the occurrence's date+time:
`<slug>@YYYY-MM-DDTHHMM`. (Per-occurrence dedup key; an Ateneu activity is a
single occurrence today, but qualifying is cheap and future-proofs repeats.)

## Quirks

- Currently only **1** future concert (2026-06-10, Quartet Vivancos). The venue's
  classical programming is genuinely sparse; most months may have 0–2 concerts.
  A low/zero count is expected, not a scraper failure.
- Cancelled sessions keep a `[Sessió anul·lada]` / `[Places exhaurides]` prefix in
  the title; left as-is (we don't drop them).
