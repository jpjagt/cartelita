# Filmhuis Cavia — source map

Venue slug: `filmhuis-cavia` (Amsterdam). Single-category venue: **film** — a
volunteer-run arthouse cinema at Van Hallstraat 52-1. Member of Amsterdam's
`film` list (whitelist `film`). Not covered by `jazzin_amsterdam.py`.

Own site: `https://www.filmhuiscavia.nl/` (Concrete CMS, fully server-rendered;
no JSON API, no JSON-LD).

## List URLs

- The programme is **one hand-edited WYSIWYG page per month**:
  `/programma/<maand>-<yyyy>` (Dutch month name, e.g. `/programma/oktober-2026`).
- Discovered from the site nav (`month_urls()` on the homepage: any
  `/programma/<maand>-<yyyy>` link). Past months are taken down (404), and the
  next month appears in the nav once published — so the nav is the index.
- Other `/programma/<slug>` nav links are **detail/series pages**, not months.

## Data source (month page, `.col-content`)

The page opens with an index `<table>` ("Do. 01 | <a href="#anchor">title</a>"),
then one **section per screening**, each starting with `<hr id="<anchor>">` and
running to the next `<hr>`:

| Field            | Source |
|------------------|--------|
| `start_date`/`start_time` | first `<p>` of the section, first `<br>`-line: `"Donderdag 1 oktober, 20:00"`. Day numbers before the Dutch month name (several → one row per day), optional year and `HH:MM` after it. Year from the page slug (a `januari` on a `december` page rolls over). |
| `title`          | the section's `<h2>` |
| `annotations`    | the header's uppercase type label (`DOCU`/`SPECIAL`/`CLASSIC`/`CONTEMPORARY`/`SEX POSITIVE`, title-cased) + any `<h3>` **before** the `<h2>` (series kicker: "Brazil Unfiltered", "Première", "Cavia in Concert at Nassaukerk"). `<h3>`s after the `<h2>` are subtitles, ignored. |
| `language`       | credits line (first `<p>` after the `<h2>` containing `|`: `"Director | 1984 | Brazil | 119’ | EN subtitles"`) → the segment mentioning subtitles/dialogue/language/silent, verbatim (`"EN subtitles"`, `"no dialogue"`, `"silent, no language with live score"`). None when there is no credits line. |
| `image_url`      | first `<img src>` in the section |
| `source_url`     | the section's `MEER→`/`MORE→` link if it points to a same-site `/programma/...` page (may carry a `#fragment`), else `<month page>#<hr id>` |
| `external_id`    | `<hr id>@YYYY-MM-DDTHHMM` (anchor slugified title if the hr has no id) |
| `category_slugs` | always `["film"]` |
| `price`          | see below |

## Price rule

The sidebar (`.col-sidebar`) states the house price: *"Toegang 5 euro, tenzij
anders vermeld"* → parsed into the fallback (`"5€"`). Overrides are prose: a
`<br>`-line **starting with** `Tickets`/`Ticket`/`Entrance`/`Entree`/`Toegang`/
`Kaartjes` (optionally after an `NL`/`EN` marker):
1. in the month-page section itself (e.g. "Entrance: Donation-based (Cineville not valid)"), else
2. on the section's MEER→ detail page (fetched; restricted to the `hr#fragment`
   section when the link has a fragment, e.g. `brazil-unfiltered#food-...`), else
3. the house price.

Line normalization: amounts (`€8`, `8 euro`) → highest one (`"8€"`, `"8,50€"`);
`free`/`gratis` → `"free"` (checked before donation: "Ticket: free (donations
are welcome)" is free); `donat…` → `"donation"`; `uitverkocht`/`sold out` →
`"sold-out"`. Lines like "Free entrance to the party" or "Sliding scale: €3 to
€10" (the meal) don't start with an admission keyword and are ignored.

## Quirks

- Content is hand-typed; expect `&nbsp;`, stray `<br>`, nested `<strong>`.
  Lines are built by turning `<br>` into newlines (inline tags joined, not split).
- "Cavia in Concert" screenings can take place **off-site** (Oct 2026:
  Le Révélateur at the Nassaukerk, De Wittenkade 111). Still Cavia programming;
  kept, and the `<h3>` kicker "Cavia in Concert at Nassaukerk" is an annotation.
- Multi-film evenings (e.g. the Myanmar fundraiser, 15:00 + 16:15 films) are one
  section → one event at the header time.
- Detail pages have `<hr id="">` (empty) dividers; harmless.

## Verification

Last verified: **2026-10-10 via HTTP cross-check.** Live scrape: 18 events,
2026-10-01 → 2026-10-31 (one month page published: `oktober-2026`). Coverage:
start_time 18/18, price 18/18 (14× house `5€`, `8€`, `10€`, `donation`, `free`),
language 16/18, image 18/18. Independent check: regexed the raw month page's
index table (day + anchor), header times and `<h2>`s — all 18 rows agree on
date/time/title (0 mismatches). Price overrides checked by grepping the detail
pages: Révélateur "Tickets : €8 (or Cineville)", objects-speak "Tickets (€10)
include a shared meal" / "Regular tickets (€7)", Myanmar "Entrance:
Donation-based", closing event "Ticket: free (donations are welcome)".
