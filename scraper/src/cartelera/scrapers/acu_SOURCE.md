# ACU — source map

Venue slug: `acu` (Utrecht). Categories **alternative**, **club**, **film**;
lists whitelisted per category. Voorstraat 71 (political-cultural centre,
ex-squat). The plan proposed pop too; ACU's own labels have no pop programme
(its bands are punk/hardcore/noise), so pop is not used.

Client: plain httpx with the Cartelita UA. One request.

## List URL

`https://acu.nl/agenda` — server-rendered `ul#Agenda > li.AgendaEntry`, every
upcoming event. The `li` class list holds the venue's own filter labels (same
names as the page's `#filter=.<label>` buttons).

| Field | Source |
|---|---|
| `external_id` | URL path after `/events/` (`20261016/nothing-works-…`, date-qualified) |
| `start_date` | URL date (`/events/YYYYMMDD/`), fallback `.AgendaMonth/.AgendaDay/.AgendaYear` |
| `title` / `description` | `.pseudo-h2` / `.pseudo-h3` (subtitle) |
| `start_time` | `ul.AgendaDetails` "Start:" (fallback "Door:") |
| `price` | `.EntranceFee`: "€ 8/12" → `format_eur_range` (`"12€"`; "€ 5/15" → `"5–15€"`), "It’s Free!" → `"free"`, "Donation based" → `"donation"` |
| `annotations` | the filter labels (minus recurrent/weekly) |
| `category_slugs` | bands/loud/noise/folkpunk/table-gazing → alternative; dance-nights/electronic → club; movies → film (several possible). Unlabelled entries → alternative |

## Exclusions (by the venue's labels)

- Entries with none of the programme labels above: daytime "Koffie
  verQueerd", Queer D&D nights, The Barricade (food/info-talks), info talks,
  Draadverbinders (tables/handwork), drag shows (theater), art, quiz,
  karaoke-only.
- Participatory formats even when also labelled bands: `jam-sessions`,
  `open-stage-and-poetry` (Flying Carpet Jamsessie, Int'l Open Stage),
  `workshops`, `quiz`.
- Placeholder/joke entries dated >2 years ahead ("The meeting that never
  happened", 2040/2057).
- Duplicate posts of one occurrence (same title/date/time, e.g.
  `eectronic-open-stage-23`/`-24`): first kept.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 25 events,
2026-10-16 → 2027-03-11; time 25/25, price 25/25. Independent check: first 10
events' detail pages (info block: Start/Door, Entry / Free / Donation) — 10/10
agree.
