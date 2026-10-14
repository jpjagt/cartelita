# Asunción — build plan and venue ownership

Date: 2026-10-14. Status: **launched** — website-sourced venues only. The
city is in `seed.CITIES` (`asuncion`, "Asunción") and in
`web/src/lib/cities.ts`. Next step: the Instagram-only venues (below).

Rules: the same as `docs/nl-cities-plan.md` — curation and quality over
exhaustiveness (only the source's own structural signals, never title
keywords; every exclusion recorded in the scraper's SOURCE.md), one owning
source per venue (aggregators as whitelists), globally unique venue slugs,
honest User-Agent (`cartelera.scrapers.http` `CARTELITA_*`), and the
`writing-a-scraper` skill.

## City config (launched)

`web/src/lib/cities.ts`:

```ts
asuncion: {
  slug: "asuncion",
  name: "Asunción",
  locales: ["es", "en"],
  defaultLocale: "es",
  defaultList: "film",
  timezone: "America/Asuncion",
},
```

- **Default list `film`**: most of the city's website-sourced programme is
  film (Cine de Barrio + the cultural centres' cycles).
- **Time zone**: Paraguay abolished DST and moved to permanent UTC−3 in
  October 2024; tzdata ≥ 2024b models it. Checked 2026-10-14: Python
  `zoneinfo` (system tzdata) and Node 24 (ICU tz 2025b) both give UTC−3 for
  January and July 2026/2027. A runtime with tzdata < 2024b would show
  UTC−4/−3 swings (old DST rules) — keep the production images' tzdata
  current. All sources give local wall-clock times except Alianza Francesa's
  iCal (UTC, converted with `ZoneInfo("America/Asuncion")`).
- No new i18n: `es`/`en` dictionaries already exist (Barcelona).

## Research summary (2026-10-14, verified live)

- **Cine de Barrio** (cinedebarrio.com): Framer, server-rendered; `/eventos`
  lists films, each detail page lists its screenings with date, time, PYG
  price and a per-screening Tally ticket id. 20-seat auteur cinema. ✓ built.
- **ICPA – Goethe-Zentrum** (www.icpa-gz.org.py): The Events Calendar REST
  API; works with httpx + Cartelita browser UA (no curl_cffi needed). Mostly
  workshops; programme = film cycles, concerts, the odd dance/theatre item.
  ✓ built (reuses `_tribe_events.py`).
- **Alianza Francesa Asunción** (alianzafrancesa.edu.py): WordPress + Modern
  Events Calendar; `wp/v2/mec-events` lists posts (no dates); MEC's per-event
  iCal export (`?method=ical&id=`) has UTC times + category names. AF Cine
  weekly + Paraguayan film cycle → film; Teatro → theater. Monthly batches,
  so 0 upcoming between batches (true on 2026-10-14). ✓ built.
- **CCE Juan de Salazar** (cceasuncion.aecid.es): AECID Liferay agenda with a
  JSON listing resource + structured detail fields (Categoría, Fecha,
  Horario, Lugar). ✓ built as the reusable `_aecid.py` + thin
  `cce_asuncion.py` (the same platform serves CCE Montevideo, Lima,
  Guatemala, Tegucigalpa, Santiago).
- **cultura.asuncion.gov.py** (municipal agenda — Teatro Municipal Ignacio A.
  Pane, Manzana de la Rivera, Centro Paraguayo Japonés): ✗ **not built**, see
  Exclusions.
- PYG prices: new helpers in `scrapers/price.py` (below).

## Venue ownership

| Venue | Slug | Categories | Owner (source) | Status |
|---|---|---|---|---|
| Cine de Barrio | cine-de-barrio | film | cine-de-barrio | live: 17 screenings 14–31 Oct |
| ICPA – Goethe-Zentrum | icpa-gz | film, classical, dance, theater, kids | icpa-gz | live: 1 concert (23 Oct) |
| Alianza Francesa de Asunción | alianza-francesa-asuncion | film, theater | alianza-francesa-asuncion | live: 0 (October batch not yet posted) |
| CCE Juan de Salazar | cce-asuncion | film, theater, kids | cce-asuncion | live: 5 screenings 28–31 Oct |
| ~~Teatro Municipal Ignacio A. Pane~~ | — | — | (cultura.asuncion.gov.py) | not built |
| ~~Manzana de la Rivera~~ | — | — | (cultura.asuncion.gov.py) | not built |
| ~~Centro Paraguayo Japonés~~ | — | — | (cultura.asuncion.gov.py) | not built |

No aggregator runs in Asunción yet, so there are no whitelists to keep apart.
Cross-venue overlap to know about: the cultural centres co-program cycles at
each other's rooms. ICPA and Alianza Francesa drop items not at their own
venue (structured venue/location field); CCE's "Lugar" is per item, not per
date, so a multi-place cycle can list a partner-venue date under CCE (e.g. 5
Oct 2026 at Cine de Barrio). See each SOURCE.md.

## Exclusions (and why)

- **cultura.asuncion.gov.py — not built.** The municipal site is a news/events
  CMS with **no type or genre signal**: its only "category" is the owning
  institution (a logo per card / `category_id` 1 Manzana, 2 Teatro, 3 IMA,
  4 CPJ, 9 Asu Cultura). Upcoming items mix opera and ballet with a
  dramatized guided tour (Dramatour), a dance teaser on the theatre's steps,
  exhibitions, book launches and library news; CPJ's feed is course
  enrolment. Keeping concerts/theatre/dance and dropping exhibitions/tours/
  launches would need title keywords. The Teatro's own ensemble filter
  (`/teatro?grupo=osca|ocma|bcmm`, which would map to classical/dance)
  returns empty pages or HTTP 500. Revisit if the site gains a working
  ensemble/genre filter, or source these venues from their Instagram.
- Per-source exclusions (workshops, talks, exhibitions, reading clubs,
  off-site partner events, Música-only nights at ICPA, CCE "Música / Sonido"
  without a genre) are in each `*_SOURCE.md`.

## Deferred: Instagram-only venues (next step)

Candidates for an Instagram source (like Yerevan's), to confirm one by one
that they have no usable website agenda before building. The research
hand-off's own list was not available when this doc was written; these come
from venues seen in the sources above and in press theatre listings (Hoy,
2026):

- Sala La Correa (independent theatre/dance; hosts CCE co-productions)
- Arlequín Teatro
- Sala Piloto / El Otro Teatro / Casa Sigilos / Casa Argentina
- Teatro Salemma Carmelitas
- Galpón del Pasaje Molas
- Teatro Municipal Ignacio A. Pane and Manzana de la Rivera (via the
  municipality's `@culturaasu` or the venues' own accounts), given the
  municipal website can't be curated (above)
- Casa Bicentenario de las Artes Visuales (hosts CCE film screenings)

## PYG price format

`scrapers/price.py`: `format_pyg(40000)` → `"40.000₲"` (Paraguayan
dot-thousands, ₲ glued after the number like `"12€"`/`"5000֏"`; 0 →
`"free"`), `format_pyg_range(lo, hi)` (2× rule: `"40.000–120.000₲"` only when
hi ≥ 2·lo, else the highest), `pyg_amounts(text)` / `pyg_price(text)` for
free text ("Gs. 80.000", "Gs380000", "40.000 PYG", "₲ 50.000", "30.000 Gs.",
"150.000 guaraníes" — a currency marker is required, bare numbers are never
read as prices). Never emit "Gs"/"PYG".

## Launch checklist (done 2026-10-14)

1. `seed.CITIES` += `("asuncion", "Asunción")`.
2. Four sources with fixtures, tests and SOURCE.md; live field-by-field
   cross-check; cold-start E2E on a scratch DB (per-day counts match live).
3. `web/src/lib/cities.ts` entry (above); `pnpm build` against Asunción data:
   `/asuncion/es/film` renders, Spanish dates ("miércoles, 14 de octubre"),
   ₲ prices.
4. The nightly run picks the sources up automatically (registry); no cron
   change needed.
