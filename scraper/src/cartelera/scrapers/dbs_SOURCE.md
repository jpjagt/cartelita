# dB's — source map

Venue slug: `dbs` (Utrecht). Categories **pop**, **alternative**; lists `pop`
and `alternative` (whitelisted). Vlampijpstraat 63, Zuilen (site
`dbstudio.nl`, Stichting Ruis).

Client: plain httpx with the Cartelita UA. Shared Tribe helper:
`_tribe_events.py` (also used by `basis_utrecht`).

## Data source

The Events Calendar REST API:
`https://dbstudio.nl/wp-json/tribe/events/v1/events?per_page=50` (2 pages,
followed via `next_rest_url`; server window today → +2 years).

| Field | Source |
|---|---|
| `external_id` | event `id` (one post per occurrence) |
| `title` | `title` (HTML-unescaped) |
| `start_date`/`start_time` | `start_date` (local); `all_day` → no time. Matches the detail page "Aanvang" |
| `price` | Tribe `cost`/`cost_details` — empty for every show (tickets on Stager, not fetched) → None; "Gratis" → `"free"` |
| `image_url` | `image.url` |
| `annotations` | `categories[].name` minus Concert/Cafe, plus `tags[].name` |
| `category_slugs` | the venue's own categories: a pop label (Pop, Dream Pop, Singer Song Writer) and nothing else → pop; pop label plus other genres → pop + alternative; otherwise (punk, metal, garage, psych, noise, series names, no label) → alternative |

## Exclusions (by the venue's categories)

- Bar nights: `Karaoke`, `PopPubQuiz Live`, `Metal Quiz & Karaoke`,
  `Tap Takeover`, `Bier specials`, and any `Cafe` item without `Concert`
  (4 events at last check). A Cafe+Concert item (AZC viering) is kept.

## Quirks

- 23 of 62 events have an empty `venue` — all are at dB's (no other venue
  occurs); not used.
- "GPLR BANDDAG: Bandmatching + Workshops" (band-contest day) is kept: its
  category (`De Grote Prijs van Leidsche Rijn`) is the contest series, no
  structural workshop signal.
- One Tribe start time looks like a typo at the source (SPITE HOUSE 08:00);
  kept as stated.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 58 events,
2026-10-14 → 2027-05-13; time 58/58, price 0/58 (none on the site), 54
alternative-only / 1 pop-only / 3 both. Independent check: first 8 events'
detail pages ("Aanvang", no € on the page) — 8/8 agree.
