# Stadsschouwburg Utrecht — source map

Venue slug: `stadsschouwburg-utrecht` (Utrecht). Categories theater, dance,
kids, classical, pop — each with a list membership whitelisted to itself.
Shared helpers + ownership notes: `cre8ion_SOURCE.md`.

## List URLs (httpx, server-rendered)

- `https://stadsschouwburg-utrecht.nl/agenda?page=N` — ONE row per
  performance (`ul.events-list > li.paging-container`), 30 per page, ~20
  pages (~600 performances). Pager: `.page-numbers .page-number`.
- Kids set: `/agenda?tag=spruitjes-0-tot-4-jaar&tag=kinderen-4-tot-12-jaar&page=N`
  (the site's own age filter, union of 0–4 and 4–12) → programme URLs.
- Language set: `/agenda?tag=language-no-problem&page=N` → programme URLs.
- Detail: the row's `h3.title a[href]` (`/agenda/seizoen-2026-2027/<slug>`),
  fetched once per programme (only for kept rows not already sold-out/free).

## Fields

| Field | Source |
|---|---|
| `title` | `h3.title a` |
| `start_date`/`start_time` | `time[datetime]` "14-10-2026 20:00:00" |
| `description` | `p.subtitle` (company) — `p.subtitle.oneliner` |
| `category_slugs` | `span.tag` genre labels (see mapping) + `kids` from the age filter |
| `annotations` | genre labels + `a.tag` festival/series labels ("Warming Up Festival", "huisgemaakt") + flags (`.date-wrapper-mobile > span`: reprise, première, dernière) |
| `price` | list button text: `uitverkocht` → `sold-out`; `vrije inloop`/`bestel gratis kaarten`/`vrij te bezoeken` → `free`; else detail `#ticket-blocks-container .ticket-block` matching date+time: the **bold** group of `.price-text` ("€ 25,00 / € 21,00 / € 15,00" = seat ranks) on the 2× rule (`25€`; Cats 49–99 → `49–99€`); the non-bold "t/m 18 jaar € 12" youth tier is skipped. `€ 0,00`/`gratis` → `free`. |
| `language` | `"Language no problem"` when the programme is in the language-no-problem filter |
| `image_url` | row `img[src]` |
| `external_id` | `data-detail-link` (per-performance id) `@YYYY-MM-DDTHHMM` |

## Category mapping (genre labels, never titles)

- Toneel, Cabaret, Muziektheater, Musical, Show, Mime, Spoken word, Circus → `theater`
- Dans → `dance`; Opera → `classical`
- Muziek → `pop`, only when the row has no stage genre (Popronde, Le Guess
  Who?, concerts); "Muziek, Dans" baby shows are just `dance`.
- In the kids age filter → `kids` (added to the genre categories).

## Exclusions (curation)

- **Theatercollege** (lectures) and **Amateuruitvoering** rows — always out.
- Rows whose only genres are **Verdieping** (talks, workshops) and/or
  **Foodprogramma** (tastings) — out; they stay when combined with a stage
  genre ("Lachen met Volle Mond" = Foodprogramma + Cabaret).
- Rows with no genre at all (Warming Up Festival swap shop / exhibition /
  café items, a ticketshop.nl Sint show) — out.
- Location **KABUL à GoGo** (owned by `kabul-a-gogo`) and **Fort aan de Klop**
  (off-site) — out.
- Cancelled rows (`geannuleerd` tag/button) — out.

Live 2026-10-14: 593 rows → 431 kept (≈90 KABUL, 8 Fort aan de Klop, 8
cancelled, ≈55 talks/lectures/food/festival-side rows). Mainstream touring
cabaret/musical/show is kept (the venue labels it theatre): of the kept rows
~94 Cabaret, ~18 Musical, ~8 Show.

## Verification

Last verified: **2026-10-14 via HTTP cross-check** — page 2 re-parsed with
throwaway regexes (title, `time[datetime]`, `span.tag`, hall) and each
programme's detail `.price-text <strong>` for the matching date: 8/8 rows agree
(the one missing row is a Verdieping-only talk, excluded by design). Live run:
431 events 2026-10-14 → 2027-07-11; time 431/431, price 430/431 (Le Guess Who?
festival pass has no price on its page), language 17.
