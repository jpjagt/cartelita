# arten — source map

Independent chamber theatre in Yerevan (founded late 2022). Next.js (App
Router) site, trilingual: `/hy`, `/ru`, `/en`. The programme lives at
`/{lang}/afisha` ("Programme"), which lists every upcoming dated occurrence —
one card per occurrence, server-rendered (plain httpx works, no browser).

## URLs

- Canonical list: https://www.arten.theater/hy/afisha (hy = Yerevan default
  locale; the site itself is fully trilingual with no clear primary).
- Translations: https://www.arten.theater/ru/afisha and
  https://www.arten.theater/en/afisha — same cards, same `key`s, translated
  title/byline. Zipped to the canonical events by `key`.

## Data source

The page embeds its card data twice:

1. **RSC flight data** (`self.__next_f.push([1,"..."])` script chunks) — THE
   source we parse. Concatenate the chunk payloads (each decoded as a JSON
   string), find the `[{"key":...}]` array, bracket-scan to its end, and
   `json.loads` it. Each card object:
   - `key` — stable per-occurrence id embedding the date, e.g.
     `dances-for-health-2026-08-23`, `2026-08-23-osen-patriarha` → `external_id`
     (`arten-<key>`) and `start_date` (regex `\d{4}-\d{2}-\d{2}`; the display
     date string carries no year).
   - `title`, `byline` (credit line, e.g. "Ulyana Kirpichenko") → title,
     description.
   - `date` — display string `"<weekday/date> · 14:30–16:00 · 2000 ֏"` →
     start/end time (regex) and price (the segment after the last `·` that
     isn't the time). `֏` normalized to `AMD`.
   - `href` — `/{lang}/performances/<slug>` for performances, `/{lang}/projects`
     for recurring projects (e.g. Dances for Health) → source_url (absolute).
   - `photo.src` — direct S3 URL → image_url.
   - `ticketUrl` — external tickets (tomsarkgh.am) → annotation.
   - `status`/`statusLabel` — usually `"$undefined"`/null (RSC's undefined
     marker). Presumed to flag sold-out/cancelled; a status containing
     "sold"/"распро"/"վաճառ" maps price → "sold-out" (never yet observed live).
2. JSON-LD `TheaterEvent` scripts — one per card, in the same order; carries
   ISO `startDate` and (only for ticketed events) offers. NOT used: it omits
   price for non-ticketed cards and end time everywhere; the RSC key + date
   string cover everything.

## Field notes

- **Category**: everything the venue programmes (performances, open
  rehearsals, lectures, projects) → `theater`. No film/kids events appeared in
  the programme as of 2026-08-18 and the cards carry no category field; if the
  venue starts programming them, a discriminator must be found (likely `href`
  path) and the venue's seed memberships extended (see AGENTS.md multi-category
  pattern).
- **Price**: AMD display text, e.g. `2000 AMD`, `5000 AMD`. Free events not
  yet observed; "free"-word normalization for hy/ru/en is in `_normalize_price`.
- **Language**: not stated per event anywhere on the site → always None.
- **Venue**: single venue ("arten", 2 Lusinyants St) — cards carry a venue
  label but it is always "arten".
- Past dates are filtered defensively (`today` in Asia/Yerevan), though the
  afisha only lists upcoming.

## Quirks

- The card `href` for recurring projects is the generic `/projects` page, so
  many events share one source_url — external_id (tier-1 dedup) keeps
  occurrences distinct.
- Address (2 Lusinyants St, Yerevan) from the JSON-LD; Instagram:
  https://www.instagram.com/arten_theatre/.

Last verified against the live site: 2026-08-18, verified via HTTP fetch
(browser unavailable — `browser-use` 3.0 required attaching to the user's real
Chrome via remote-debugging, which needs manual approval; per policy this was
not attached). Live `httpx.get` of all three `/afisha` pages parsed with the
scraper's own `_extract_cards`/`parse_afisha` and diffed field-by-field against
the raw RSC card data: 9 events (2026-08-23 through 2026-10-11), all `theater`
(one-off performance "Осень Патриарха"/"Պատրիարքի աշունը" 5000 AMD/19:00, plus
8 weekly "Dances for Health" occurrences 2000 AMD/14:30–16:00). Every card's
title (all 3 langs), date, time(s), price and href matched the scraper's
parsed output exactly; ֏→AMD normalization confirmed on live data
("2000 ֏" → "2000 AMD"). No film/kids events present on the live programme —
single-category (theater) setup confirmed still correct.
