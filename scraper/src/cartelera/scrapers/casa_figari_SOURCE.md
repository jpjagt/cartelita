# Casa Figari — scraper source map

Last verified against live site: 2026-06-01.

**Venue:** Casa Figari (Carrer Torrent de l'Olla, 141, Barri de Gràcia, Barcelona 08012).
Squarespace site. Open Tue–Thu 20:00–02:00, Fri–Sat 20:00–02:30.
**Categories produced:** `jazz` (live concerts, jam sessions) and `club` (DJ nights / vinyl sessions).

## Important caveat: image-only agenda

Casa Figari publishes its programme **exclusively as a weekly PNG/WebP image**
(`figari+2026+feed.png`) embedded in the homepage. There is no HTML event list,
no JSON-LD, no calendar API. The site only shows the **current week** (typically
Tue–Sat, ~10 events). The scraper MUST be run weekly to capture new events.

## Data source

- **Page URL:** `https://www.casafigari.com/inicio` (the Spanish-language home page;
  `/home` is the English version and works equally well)
- **Schedule image:** found in `section[1]` of the page HTML — the only `<img>` in
  that section whose `src` contains `figari` or `feed`. The image URL is a
  Squarespace CDN URL, typically:
  `https://images.squarespace-cdn.com/content/v1/6634fdcb98d4b0328e79eadc/<hash>/figari+2026+feed.png`

## Per-field mapping

The schedule image has a two-column layout:

| Column | Content |
|--------|---------|
| Left (x < 380px) | Date (`DD/MM`), time(s), price |
| Right (x ≥ 380px) | Artist name, genre/description |

Extraction uses Tesseract OCR in TSV mode (bounding boxes per word). Words are
grouped into y-bands (20px buckets) and separated into left/right columns by the
x-coordinate threshold (380px).

| Field | Source |
|-------|--------|
| title | right-column text on the time/date row (or the following row if OCR splits it) |
| start_date | left-column `DD/MM` date token; year = current year (next year if >90 days past) |
| start_time | left-column time token (`HH:MM`, `HHH`, `HHHH`); the "& 22H" second-show marker is a continuation and NOT a separate event |
| price | left-column text matching `\d+€` or `entrada libre` |
| category | see discriminator below |
| annotations | right-column description / genre text |
| source_url | `https://www.casafigari.com` (no per-event detail page) |
| external_id | `YYYY-MM-DD_HHMM` (date + start time, sufficient to dedup within a week) |

## Category discriminator

- `club` if title or description matches (case-insensitive):
  `strictly vinyl`, `discoth`, `dj \w`, `tbc dj`, `listening session`,
  `vinyl sharing`, `open decks`
- `jazz` for everything else (live concerts, jam sessions)

The discriminator targets the actual content description — NOT a title keyword like
"DJ" alone, because future events might have jazz acts mentioning a DJ warm-up.
The key discriminators are "Strictly Vinyl Discotheque" (for late DJ slots),
"Vinyl sharing experience" (OPEN DECKS), and "Listening session" (WORLD GROOVE ON VINYL).

## Quirks

- **Image-only**: No structured HTML data exists. If the site redesign changes
  the image layout or removes the weekly feed image, the scraper will fail silently
  (no events). Monitor by checking `len(events) >= 5` on each run.
- **WebP disguised as PNG**: Squarespace serves the image as `image/webp` even
  though the filename ends in `.png`. PIL handles this transparently.
- **Two-show format**: Most evenings have 2 shows (e.g. 20:30 live act + 23H DJ
  set). The "& 22H" text on some days indicates a second concert set at 22:00 for
  the same band — this is NOT a separate event; it's additional performance info.
- **OCR on first event is more spread out**: The top event in the image has more
  vertical spacing between date/time/price/artist rows due to the image layout.
  The parser handles this with the title-continuation logic (empty title → next
  text row becomes title).
- **Tesseract path restriction**: Tesseract on macOS cannot read from `/tmp/` paths
  under certain sandbox configurations. The scraper writes the temporary OCR input
  file to `~/.cache/cartelera/casa_figari_ocr.png`.
- **Event count**: typically 10 per week (2 per night × 5 nights: Tue–Sat).
  Price coverage: 100% (all events include price). Annotations coverage: 100%.

## Seed requirements

**Venue slug:** `casa-figari`
**Display name:** Casa Figari // Bar de Jazz
**Address:** Carrer Torrent de l'Olla, 141, Barri de Gràcia, Barcelona 08012
**Site URL:** https://www.casafigari.com
**Category slugs produced:** `jazz`, `club`
**Category lists to add this venue to:**
  - Jazz list → per-venue whitelist category: `jazz`
  - Club list → per-venue whitelist category: `club`
