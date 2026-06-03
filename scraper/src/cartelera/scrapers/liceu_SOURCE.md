# Gran Teatre del Liceu — source map

last verified: 2026-06-02

## Venue
- slug: `liceu`
- name: Gran Teatre del Liceu
- city: barcelona
- address: La Rambla, 51-59, 08002 Barcelona
- site: https://www.liceubarcelona.cat

## List URL / data source
The public programme page is
`https://liceubarcelona.cat/ca/programacio?view=itemsListView&set=Espectacles&buscadorString=&category=all`.
It is a Drupal site whose programme list/calendar is rendered **client-side** by
`themes/custom/liceu_2024/js/program/programationViewLiceu.js`; the static HTML
carries no event cards. That script fetches a single clean static JSON document:

```
https://liceubarcelona.cat/sites/default/files/programme.json
```

This JSON is the scraper's sole, robust data source (no per-event detail fetches).
`parse_programme(json_text)` is the pure parse function.

### JSON shape
Top-level dict with keys `productions` and `subscriptions` (season-ticket bundles
we ignore — they carry only multi-show package prices, not per-event prices).

`productions` is a `{id_str: production}` map. A **production** record:
- `id` (str), `title` / `subtitle` / `url` — each a `{ca, es, en}` dict.
- `categories` — `{cat_id: {ca, es, en}}` map (the venue's taxonomy; see below).
- `main_image` — site-relative image path.
- `sessions` — list of OCCURRENCES; each `{id, date, turns, sale_link, ...}`.
  - `date` is a unix timestamp (see **Timestamp quirk** — it is offset).
  - `turns` carries the subscription label (e.g. "Abonament E") — annotation only.
- `first_session` / `last_session` — bounding timestamps.
- `sell_tickets`, `sponsors`, `sale_url`, `buy_button_alternative` — unused.

## Per-field mapping
- **title** ← production.title.ca (canonical); es/en → translations.
- **subtitle** ← production.subtitle.ca → first annotation.
- **start_date / start_time** ← session.date, decoded with the +2h correction
  below. All sessions carry a real time (no midnight all-day sentinels).
- **source_url** ← `https://www.liceubarcelona.cat` + production.url.ca
  (es/en URLs → per-translation source_url).
- **price** ← **None** (NOT in the feed). Per-event prices live only on each
  production's detail page (e.g. /ca/nozze-di-figaro shows "20€ / 10€ / 8€");
  fetching 200+ detail pages per run is too heavy, and None is a valid value per
  the price convention. Documented gap, not a silent drop.
- **image_url** ← `https://www.liceubarcelona.cat` + production.main_image.
- **category_slugs** ← mapped from production.categories (see Category rule).
- **annotations** ← subtitle + the non-genre taxonomy tags (LiceUnder35,
  Liceu de les arts) + the session's subscription turn name. Never category slugs.
- **external_id** ← `f"liceu-session-{session.id}"`. The session id is already
  per-OCCURRENCE (one per performance date), so no date qualification is needed.
- **translations** ← es/en title/subtitle/url when present and non-null.

## Timestamp quirk (IMPORTANT — verified, not a guess)
The feed's `session.date` timestamps are **2 hours behind** the wall-clock the
venue actually displays. For "Le nozze di Figaro" the live detail page
(/ca/nozze-di-figaro, "Dates i entrades") shows 5 June = 19:30, 7 June = 17:00,
8 June = 19:30, 13 June = 19:00, 14 June = 18:00. The same sessions in the feed,
read in Europe/Madrid, come out exactly 2h earlier (17:30 / 15:00 / 17:30 /
17:00 / 16:00). The site's own JS does `new Date(date*1000)` then `getHours()`
in a Madrid browser plus an additional transform we couldn't locate; rather than
guess that code, the offset was confirmed **statistically across all 535 sessions**:
the `Madrid + 2h` reading clusters on real event times (peaks at 19:00 ×196 and
20:00 ×167, matinees at 12:00, late recitals 21:00/22:00), whereas the raw Madrid
reading peaks implausibly at 17:00/18:00. The correction holds across DST (winter
UTC+1 sessions also land on plausible 20:00/21:00 slots).

**Rule:** `start = datetime.fromtimestamp(ts, Europe/Madrid) + 2h`; use its date
and time. If the venue ever fixes the export, the hour distribution will shift
back to 17:00/18:00 — re-verify against a detail page then.

## Filtering
Emit a session only when its `date`, corrected, is **today or later** (the feed
holds past seasons too — 256 of 535 sessions are stale 2024/25 dates). Skip
sessions/productions with a missing title or url.

## Category rule
Liceu is primarily an opera house but programmes several genres. Mapping from the
venue's `categories` taxonomy (a production may carry several; the first match in
this priority order wins):

1. **Dansa** → `dance`
2. **Petit Liceu** / **LiceuAprèn** → `kids`
3. **Promotores externes** → `pop` (external promoters renting the hall — pop /
   singer-songwriter concerts: Pablo López, Carminho, Hermanos Gutiérrez, etc.)
4. **Òpera**, **Òpera versió concert**, **Microòperes**, **Concerts i recitals**,
   **Concerts de cambra**, **Ciutat de Clàssica**, **Espectacle performàtic**, and
   anything else → `classical` (default).

Priority puts the genre that best describes the event first: a Dansa production
tagged also Petit Liceu is dance; a kids opera is kids. The cross-cutting audience
/ series tags **LiceUnder35** and **Liceu de les arts** are NOT genres — they go
to annotations, never to category_slugs.

`dance`, `kids`, `pop` are NEW top-level categories added to seed.py for this venue.

## Quirks
- JS-rendered programme; we hit the static `programme.json` directly.
- The feed mixes seasons; filter to today-or-later (the venue has no per-session
  "expired" flag, so we filter by the corrected date).
- No price in the feed (see price mapping).
- Multilingual: ca/es/en titles, subtitles and URLs all present → translations.

## Verification (2026-06-02)
Live `LiceuScraper().scrape()` produced **204** upcoming events
(classical 158, kids 23, dance 17, pop 6), 100% with image + translations, all
external_ids unique, price 0% (documented — not in feed). Cross-checked the live
**calendar view** card-by-card against the scraper for the first ~10 occurrences:
titles, dates, **times** (the +2h correction reproduces 5 Jun = 19:30,
7 Jun = 17:00, 13 Jun "La torre dels somnis" = 11:00), categories and the
LiceUnder35 / Abonament annotations all agree. Pop = external singer-songwriter
concerts (Pablo López, Hermanos Gutiérrez, Carminho); dance = El trencanous /
Gran gala de dansa. es/en titles + URLs present as translations.
