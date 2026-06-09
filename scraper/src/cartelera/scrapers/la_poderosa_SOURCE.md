# La Poderosa — source map

Small, grassroots dance / live-art space in the Gothic Quarter, Barcelona.
Drupal site. **The homepage (`https://lapoderosa.es/ca`) is the canonical event
list** — it renders every current/upcoming event as a teaser card. There is NO
dedicated agenda/programació page: `/ca/programes` is editorial text about the
venue's residency programmes, not an event list, and the nav has no calendar.

## Source URL

- List: `https://lapoderosa.es/ca` (homepage)

## Data source — rendered DOM teaser cards (no JSON-LD)

No `application/ld+json` on the page. Events are Drupal node teasers.

- Card: `.node-event.node-teaser`
- Title: `.field-name-title-field h3 a` (text)
- Detail link: same `<a>` `href` (relative `/ca/event/<slug>`)
- Image: `.field-name-field-img-event img[src]`
- Type/category label: `.field-name-field-tipus-event .field-item` text
  (values seen: `Performance`, `Presentació`, `Residència`, `Trasnmissió`)
- Date — two shapes, both carry an ISO `content` attr:
  - single: `.date-display-single[content]`
  - range:  `.date-display-start[content]` (+ `.date-display-end[content]`)
  - The ISO content is like `2026-07-17T19:00:00+02:00`. Time `00:00:00` is the
    all-day sentinel -> `start_time = None`.

## Category-mapping rule

La Poderosa is a dance / live-art space; every event is movement/performance
work. All site `tipus` labels map to `dance` (the venue's core discipline).
The raw `tipus` label is preserved verbatim as an annotation so the
performance/presentation/residency distinction isn't lost. No `theater`
events were found (the "Performance" type here is body/movement live art in a
dance house, not theatre), so the scraper currently emits only `dance`.

## Price

**Price is not published anywhere** — neither on the teaser nor on the detail
page (no price/entrada field; detail body text carries no price). La Poderosa
runs on free / pay-what-you-want grassroots terms and simply doesn't list a
figure. So `price` is always `None`. This is expected for this venue; the test
asserts the reliably-present fields (date, title, url, category, image) rather
than a price floor.

## external_id

Per-occurrence key: `f"{slug}@{date}T{HHMM}"` where `slug` is the `/ca/event/`
path slug, `date` is the start date ISO, and `HHMM` is the start time (or
`0000` when the time is the all-day sentinel / unknown). Qualifying with
date+time keeps repeated occurrences of the same show distinct.

## Quirks

- Titles often carry a trailing/leading `/` separator (e.g. `NORMA PÉREZ /`,
  `SERGI FAUSTINO / EL COS I EL TEMPS`); we collapse whitespace and strip a
  dangling trailing slash.
- The page mixes upcoming and recently-past events; the scraper emits all cards
  present (no date filtering) — matches what a visitor sees.

Verified: 2026-06-09

## Last verified

2026-06-09 — live scrape returned 9 events; cross-checked the first 6 against
the homepage DOM (title / date / time / tipus / image) — all agree. Price
absent on every card, as expected. The 00:00:00 Trasnmissió card correctly
yields start_time=None.
