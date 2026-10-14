# cre8ion (Utrecht theatres) — shared notes

Three Utrecht theatres run the same agency's CMS (cre8ion, ASP.NET) with
Ticketmatic tickets; Theater Utrecht's Nuxt site sits on a cre8ion back-end too.
They are **four single-venue sources**, not one multi-venue source: each site
is its own origin with its own template, so there is nothing to share at the
request level. What is shared lives in `_cre8ion.py` (leading underscore →
`load_all()` skips it, no registry edit needed):

- `USER_AGENT` — `Mozilla/5.0 (compatible; Cartelita (+https://cartelita.july.dev)) … Chrome/141`; plain httpx works on all four (no bot protection).
- `parse_date` — Dutch list dates. SSBU has a year; Kikker/Hoge Woerd don't
  ("wo 14 oktober"): the **weekday picks the year** (the candidate year where
  that date falls on that weekday, nearest to today).
- `parse_time` — "20:00u"; 00:00 is treated as "no time".
- `amounts` / `format_tiers` (seat ranks, 2× rule) / `highest` (discount
  tiers → full price) / `row_price`.
- `parse_ticket_rows` + `match_row` — the `.ticket-row.desktop` blocks on
  Kikker/Hoge Woerd detail pages (`.date`, `.time`, `.genre` = hall,
  `.price`, and per-date `.date .label` badges), matched to a list occurrence
  by date+time (else date). `SKIP_ROW_LABELS` (Verhuur, Verplaatst,
  Geannuleerd) drop that date.
- `fetch_all` — detail pages, each distinct URL once per run, ≤ 3 requests in
  flight; a failed fetch just means no price for that programme.

robots.txt on all three cre8ion sites disallows `/mvc/` (the AJAX endpoints),
`/views/`, `/controls/` … — we only use `/agenda…` pages and detail pages.

Per-venue maps: `stadsschouwburg_utrecht_SOURCE.md`,
`theater_kikker_SOURCE.md`, `podium_hoge_woerd_SOURCE.md`,
`theater_utrecht_SOURCE.md`.

## Ownership overlaps (one owning source per venue)

The four programmes cross-list each other's shows; each source keeps only the
rows that physically play in its own venue:

- SSBU lists KABUL à GoGo's nights (the club in the SSBU building, owned by
  `kabul-a-gogo`) → dropped by SSBU.
- Kikker lists "Kikker op Locatie" / "Kikker X …" shows at Theater Utrecht
  (Boorstraat 107), SSBU and community venues → dropped by Kikker (detail
  hall not Grote/Kleine Zaal).
- Theater Utrecht lists its shows at SSBU / Kikker and its national tour →
  dropped by Theater Utrecht (only `Theater: Theater Utrecht`).
