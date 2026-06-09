# Teatreneu — Source Map

## Venue
Teatreneu, C/ de Terol, 26, 08012 Barcelona (Gràcia)
https://www.teatreneu.com

## List URL
`https://www.teatreneu.com/ca/cartellera.html`

## Data source
Two-level DOM scrape — no usable JSON-LD (only Website/Event boilerplate).

**Level 1 — Show list** (`https://www.teatreneu.com/ca/cartellera.html`):
- Show cards: `.row[data-open-espectacle]`
- Title: `a.titol` (text + href for `source_url`)
- Category tags: `.categoria` spans (e.g. `c16`=Màgia, `c17`=Teatre, `c18`=Monòlegs, `c19`=Humor, `c20`=Improvisació, `c22`=Infantil)
- Sala: `.espai a` text
- Date range: `.data-inici`, `.data-fi` (display only; not used for individual occurrences)
- Image: `a.imatge img` — first `src` attribute

**Level 2 — Session list** (per-show detail page + AJAX pagination):
- Detail page: `https://www.teatreneu.com/ca/cartellera/c/<slug>.html`
- Initial sessions: `.funcio` divs on the detail page (typically 5 upcoming)
- Additional sessions: `GET ajax.php?function=paginarFuncionsFitxaEspectacle&pageNum=N&itemID=ID&dataAnt=DATETIME&caducat=0`
  - Pages: 5 sessions each, `dataAnt` = last-seen datetime, `pageNum` increments from 1
  - Returns empty string when exhausted
- Per-session fields:
  - `external_id`: CSS class `funcio-NNNNN` on the `.funcio` div
  - `start_date`: ISO date from Google Calendar link `dates=YYYYMMDDTHHMMSSZ` on the page
  - `start_time`: `.hora span.hora` text (e.g. "20:00 h")
  - `price`: `.preu` text (e.g. "Des de 14 €" → "14€")
  - `availability`: `.hora` CSS class (`disp-alta`, `disp-mitja`, `disp-baixa`, `disp-ultimes`, `disp-no`)

## Category mapping
Teatreneu is a comedy/theatre venue. All events → `theater`.
`Infantil` tag also adds → `kids`.
All Catalan category tags (Improvisació, Humor, Monòlegs, Màgia, Teatre, Infantil) go into
`annotations` as well.

## Halls
- `Sala Xavier Fàbregas` — main stage
- `Sala Cafè Teatre` — smaller stage

Both halls → `theater` list membership (no whitelist needed, single-category venue).

## external_id
`f"{funcio_id}"` — the funcio numeric ID is unique per occurrence and guaranteed by the
venue's own system. No date qualification needed.

## Price convention
`Des de N €` → `"{N}€"` (extract the integer). "Exhaurides" / sold-out state → `"sold-out"`.

## Lookahead
Scraper fetches sessions up to 90 days from today, per show.

## Quirks
- Session dates only show `diaNom + dia + mes` (no year). Year is derived from Google Calendar
  link embedded in each session's HTML (`dates=YYYYMMDDTHHMMSSZ`).
- JSON-LD Event block has `endDate: 2024-04-19` (wrong; it's actually the original start date)
  — do not trust JSON-LD for dates.
- 13 shows active as of recon; each with ~10–50 upcoming sessions (60-day window).

## Last verified: 2026-06-09
