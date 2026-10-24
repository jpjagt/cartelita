# Soho Theatre — source map

Source slug: `soho-theatre` (London), multi-venue:

| Venue slug | Building | Spektrix `Venue` attribute |
|---|---|---|
| `soho-theatre` | 21 Dean Street, W1D 3NE | Theatre, Upstairs, Downstairs, Studio 1 |
| `soho-theatre-walthamstow` | 186 Hoe Street, E17 4QH | Soho Theatre Walthamstow |

Categories `theater`, `kids` (lists `theater`, `kids`, whitelisted).

Data: Spektrix client `sohotheatre` via `_spektrix.py` (see
`spektrix_SOURCE.md`). The client is big (~125 events, ~1,300 performances in
six months): the date window is required. No site join: sohotheatre.com show
pages embed no Spektrix ids, so events link to the Spektrix event page.

## Curation

- `WebsiteFilterCategory1` (the website's own filter): **Theatre → theater,
  Family → kids**. Left out: Comedy (~70% of the programme), Cabaret, Music,
  Podcast, unlabelled — Cartelita has no comedy category yet (see
  `docs/london.md`).
- `Venue`: only the rooms above. Dropped: Soho Theatre Pub, the Glasgow Glee
  Club (Soho's Glasgow partner), blank.

## Quirks

- Dynamic pricing (`attribute_DynamicPricing`): band prices differ per
  performance (HAM £25–28), so prices vary night to night — correct.
- The venue's own "Theatre" label includes some solo-show/talk crossovers
  (e.g. GothamChess at Walthamstow); we follow the label.

## Verification

Last verified **2026-10-24**, live: 244 performances (Dean Street theater
200; Walthamstow theater 11, kids 33), every one priced. Cold-start DB: 244
rows; renders on /london/en/theater and /kids.
