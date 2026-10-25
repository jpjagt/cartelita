# Tessitura TNEW v7 (shared helper `_tnew.py`)

London box offices on TNEW (probed 2026-10-25, all open to plain httpx with
the Cartelita browser UA): `tickets.nationaltheatre.org.uk`,
`my.sadlerswells.com`, `secure.southbankcentre.co.uk`,
`ticketing.almeida.co.uk`, `my.hampsteadtheatre.com`,
`basket.shakespearesglobe.com`, `my.oldvictheatre.com`.

## Endpoint
1. `GET https://<host>/events` — session cookies only (ASP.NET, Incapsula,
   Queue-it "safetynet" acceptance on NT / Sadler's / Globe / Old Vic;
   Southbank's GET lands in its Queue-it room yet the POST still answers).
2. `POST https://<host>/api/products/productionseasons`, JSON
   `{"startDate":"YYYY-MM-DDT00:00","endDate":"YYYY-MM-DDT00:00"}` (window =
   today + 183 days) → `{"productions":[…], "ga4DatalayerItems":[]}`.

Per production: `productionSeasonId`, `productionTitle` (HTML link),
`listingImageUrl`, `keywords` (null everywhere). Per performance: `id`,
`performanceDate` (**UTC**, "+00:00" also in summer — convert to
Europe/London; `iso8601DateString` carries the local time + offset),
`displayTime`, `performanceTitle`, `actionUrl` (`…/<prod>/<perf>`, Old Vic
`…/<slug>/<perf>`), `isOnSale`, `performanceStatusMessage` (free HTML:
"Sold out", "<h2>SOLD OUT</h2>", "Tickets Not On Sale"…), `productTypeId`
/ `productTypeName` (host-defined; the name is empty except at the Old Vic,
where it names the access provision).

## What TNEW lacks / quirks
- No price, auditorium, genre or description → every venue joins its
  website (booking links embed `<prod>/<perf>`, `events/<prod>`,
  `overview/<prod>`).
- Seating products as extra "performances" at the same time (Southbank:
  Cirque Alice "Onstage ringside tables") → `performances()` keeps one per
  (production, start).
- Not always complete: Hampstead's feed had 105 of the site's 184
  performances (priority-booking ones missing), Almeida's 150 of 189. Those
  two modules read the website only.
- Prices: the SYOS seat-map price API wasn't found (probing it got the
  Almeida host to time out — don't hammer it).

## Helper
`fetch_performances(host)`, `booking_ids(html, hosts)`, `fetch_pages(urls)`
(≤3 concurrent, dead page = warning), `ladder_price` / `price_range` (via
`price.format_gbp_range`, 2x rule), `event(perf, …)` (sold-out → price
"sold-out", external_id = TNEW perf id, product-type name → annotation).
