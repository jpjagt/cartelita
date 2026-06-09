# Teatre Grec / Festival Grec — source map

Festival Grec de Barcelona (summer festival, June–Aug). Multidisciplinary:
theatre, dance, music, circus, performance, cinema, celebration. Shows run at
many venues across Barcelona (Teatre Grec, Teatre Lliure, Sala Beckett, …).

## List URL(s) + pagination
- Schedule (all shows): `https://www.barcelona.cat/grec/en/menu/schedule`
- Paginated via `?page=N`, N = 0..5 (6 pages, ~18 cards/page, **102 events total**
  as of recon). MUST paginate all pages — page 0 alone yields only 18.
- No JSON-LD, no `__NEXT_DATA__`. Drupal-rendered DOM cards.

## Data source (CSS selectors)
Each event is `.node--type-activitat` (per list card). Fields:
- title:      `.title-activity` (text)
- source_url: `a.link-detail[href]` (relative, prepend `https://www.barcelona.cat`)
- discipline: `.discipline-item` (text) — THE category discriminator
- subtitle:   `.subtitle-activity` (text) — author/company -> annotation
- space:      `.space-activity` (text, strip trailing "Space") -> annotation (venue)
- dates:      `.dates-activity` (text) — free-form date range/list (see below)
- image:      `.wrapper-img-activity img` — `data-src` or `src` (relative)

Price is NOT on the list card — only on the **detail page**:
- `.label-content-activity` whose text is "Prices" -> sibling `.col-7` in same `.row`.
- We fetch the detail page only for price (1 request per show).

## Dates — modeling
Site gives a textual date range/list per show (NOT enumerated per-occurrence
sessions). Formats (all year 2026, June–Aug):
- `From 17 June to 5 July`, `From 1 to 3 July`, `From 1 to 9 of July`
- `1 July`, `9 and 10 July`, `25, 26, 30 June and 1, 2, 7, 8, 9 July`
- `04/07` (DD/MM), `July 9`, `Sunday, July 12`
- Catalan leftovers: `28 de juliol`, `Dilluns, 20 de juliol`, `7 and 8 de July`
- annotations in parens: `9 July (English), 10 and 11 July (Catalan)`
Parser extracts ALL (day, month) pairs; start_date = earliest, end_date = latest
(None if single day). One ScrapedEvent per SHOW (a run/season), not per occurrence
— the site exposes no per-occurrence session list, so a show is one row.

## external_id
Show slug (last path segment of source_url), e.g. `la-ruta`, qualified with
start_date: `f"{slug}@{start_date}"`. Unique per show; no occurrence collapse.

## Category mapping (discipline -> our slug)
- Theater/Performance/Circus/Celebration -> theater
- Dance -> dance
- Music -> pop   (generic live-music bucket; no sub-genre signal on site)
- Cinema -> film
Raw discipline label is also kept in `annotations`.

## Quirks
- Image/url are relative paths; prepend `https://www.barcelona.cat`.
- Price text varies: `€26`, `5 €`, `€21,50`, `€14-34`, `From €10 to €22`,
  `€30 - €42,50`, `From €12`, `€24 + handling fees`, `€12, €10 and €8`,
  `Free with prior reservation`, `Free entry (lecture) and €15 (concert)`.
  Parser: euro numbers present -> lo/hi via format_eur_range; elif free/gratu ->
  "free"; else None. (100% of shows had a price text at recon.)

Verified: 2026-06-09 — 102 events across 6 pages; disciplines Theater 40, Music 22,
Dance 18, Circus 8, Performance 7, Cinema 6, Celebration 1; price coverage 100%.

## Live verification (Phase 4) — 2026-06-09
Live scrape: 102 events (all 6 pages), price 100%, image 100%, unique external_ids.
Category split: theater 56 (Theater40+Performance7+Circus8+Celebration1), pop 22
(Music), dance 18, film 6 (Cinema). First-6 cross-check vs DOM agreed field-by-
field (title / discipline->category / date / price): La Ruta 26€, Avi 12€,
L'Albada 30€, Rasa 20€, La Truita 14–34€, L'òpera 35€.
