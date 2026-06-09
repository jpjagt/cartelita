# Espai Brossa / Centre de les Arts Lliures — Source Map

**Site:** https://www.fundaciojoanbrossa.cat  
**Venue:** Fundació Joan Brossa, C/ Flassaders, 40, 08003 Barcelona  
**Character:** Low-volume avant-garde performing-arts venue. Typically 4–8 events at any given time.

## List Page

**URL:** `https://www.fundaciojoanbrossa.cat/` (homepage)

The homepage "Què està passant" section lists all current events in
`article.news-item` cards. This is the only page that aggregates all event
types (Espectacle + Exposició + Activitat) in one place.

**CSS selectors:**
| Field       | Selector                                              |
|-------------|-------------------------------------------------------|
| Cards       | `article.news-item`                                   |
| Date string | `.flex.justify-between div:first-child`               |
| Category    | `.flex.justify-between div:last-child`                |
| Title       | `h3 span` (first match; h3 appears twice for hover)   |
| Detail link | `a[href]` (first `<a>` in the card)                   |
| Thumbnail   | `img[src]`                                            |
| Subtitle    | `h4`                                                  |
| Snippet     | `.mt-2.text-sm div`                                   |

**Category filter:** Cards with `nota-de-premsa` or `general` CSS class, or whose
category label is not in `{Espectacle, Exposició, Activitat}`, are **press releases
or news items** — excluded entirely.

**Date format:** `DD.MM.YYYY - DD.MM.YYYY` (range) or single `DD.MM.YYYY`.
Parsed with `re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")`.

## Detail Page

**URL pattern:** `https://fundaciojoanbrossa.cat/arxiu-arts-en-viu/<slug>/`
(also `/arxiu-exposicions/` and `/arxiu-pensament/` for other types)

Price is NOT available on the list page. Each event detail page has a
`.sidebar-expos` block with an "INFO ÚTIL" section that may contain:
- `Preu: N €` — explicit ticket price (e.g. Espectacles from Festival Grec)
- `ENTRADA LLIURE` / `Gratuïta` — free entry (for exhibitions)
- no price at all — unknown (e.g. venue's own productions like BLATTODEA)

**Price fallback:** For Activitat pages that embed prices in the main content body
(no sidebar INFO ÚTIL), the scraper scans `.entry-content` for euro amounts.
Example: "Casal d'estiu" has `75€` / `95€` in the body.

**No JSON-LD event data** — Yoast SEO only emits WebPage/BreadcrumbList boilerplate.

## Category Mapping

| Site label   | Our slug  | Rationale                                         |
|--------------|-----------|---------------------------------------------------|
| `Espectacle` | theater   | Experimental/avant-garde live performance         |
| `Exposició`  | theater   | Visual poetry & installation at this arts centre  |
| `Activitat`  | theater   | Workshops, talks, activations (default)           |
| `Activitat`  | kids      | When title contains "casal", "escola", "infants"  |

## external_id

The final URL slug (e.g. `blattodea`, `spafrica`). Each show has a unique slug.
Runs that span multiple nights are represented as a single row with an end_date;
no per-session expansion is done (consistent with Sala Beckett approach for runs).

## Price Convention

- Exposicions: typically `free` (ENTRADA LLIURE on detail page)
- Festival Grec co-productions: explicit price on detail page (15€ or 17€)
- Venue's own Espectacles (non-Grec): no price on page → `None`
- Activitats: varies — free or paid; extracted from body when present

## Venue Pricing Reference

https://www.fundaciojoanbrossa.cat/preus-i-descomptes/
- Espectacles: 15€ online / 17€ taquilla
- Activitats: varies by type

## Quirks

- The homepage shows both current events AND news items in the same container.
  Filter by category label (not by article CSS class alone, as news items also
  have `news-item` class but additionally have `nota-de-premsa` or `general`).
- BLATTODEA and similar venue-produced Espectacles have no explicit price on their
  detail pages — the venue directs to a ticketing external link (koobin.cat) without
  embedding the price.
- "Activació Sumari Astral" is held at an external location (Bombon Projects) and
  has no price on its page — None is correct (event may be invitation-only or free).

## Last verified: 2026-06-09
