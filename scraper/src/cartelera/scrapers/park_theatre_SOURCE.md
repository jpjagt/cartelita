# Park Theatre — source map

Venue slug: `park-theatre` (London) — Clifton Terrace, Finsbury Park N4 3JP.
New writing in Park200, Park90 and the Morris Space → `theater`; its family
shows → `kids`. Lists `theater` and `kids`, each whitelisted to its category.

Data: Spektrix client `parktheatre` (custom domain
`tickets.parktheatre.co.uk`) via `_spektrix.py` (see `spektrix_SOURCE.md`).
Show pages on parktheatre.co.uk are joined in
(`Site("https://parktheatre.co.uk/whats-on/", …/events/<slug>/)`): each embeds
its performances' full Spektrix ids. Shows the what's-on page doesn't list yet
(2026-10: Bull, Dickens' Christmas, Birdcatcher, Everything is, Festive
Friends) fall back to the Spektrix event page.

## Curation

- `Genre`: **Drama**, **Musicals**, **Comedy** (comic plays and family
  shows — stand-up has its own genre) and **One-off events** are programme.
  Dropped: **Supplementary event** (Pizzas — 349 instances — Drinks,
  programmes, cast albums, touch tours, AD headsets, captioning service) and
  **Stand-up comedy** (Cartelita has no comedy category).
- `Venue` (the room): **Park200 / Park90 / Morris Space** kept; **Events
  Elsewhere** and **Online Event** dropped (in 2026-10 only supplementary
  items use them).
- `RecommendationCategory1` (the event's primary recommendation label) =
  **Family** → `kids` (Comedy Club 4 Kids); else `theater`. Family as a
  secondary label (Miss Bennet: RecommendationCategory3) stays `theater`.

## Quirks

- The website's own cards carry richer labels ("Comedy", "Family" tags) but
  embed no structured link to them; the API's labels are used.
- `webUrl` is filled on a few events (sometimes a stale `/event/…` path); the
  site join wins when the show page is found.
- Prices vary per performance (preview / standard / peak price lists); each
  performance gets its own price list's band-default range.

## Verification

Last verified **2026-10-24**, live: 355 performances, 19 events (352 theater,
3 kids), 100% priced; 290 link to parktheatre.co.uk, 65 to the Spektrix page.
Mojo: 44 perfs 4 Mar–10 Apr 2027, evenings 19:00, matinees 14:30, "£15–35"
(previews) / "£23–48.50" / "£27–55" / "£49.50" — matches its page ("Evenings
19.00 Thu & Sat 14.30", "Tickets £15 - £55"). Cold-start DB: 355 rows.
